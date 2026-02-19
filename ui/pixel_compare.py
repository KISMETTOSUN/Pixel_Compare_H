
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from PIL import Image, ImageTk, ImageChops, ImageDraw, ImageFont
import fitz  # PyMuPDF
import os
import sys

# Suppress PaddleOCR model source check
os.environ["PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK"] = "True"
os.environ["PADDLEOCR_SUPPRESS_WARNINGS"] = "1" # Extra safety


import difflib
import math
import numpy as np
import tempfile
import webbrowser

# Gerekli kütüphaneleri kontrol et
try:
    import cv2
    CV2_SUPPORT = True
except ImportError:
    CV2_SUPPORT = False

try:
    import pytesseract
    # Tesseract yolunu belirtmeniz gerekebilir:
    # pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
    TESSERACT_SUPPORT = True
except ImportError:
    TESSERACT_SUPPORT = False

try:
    # Temporarily redirect stderr to devnull to hide connectivity warning
    stderr_backup = sys.stderr
    sys.stderr = open(os.devnull, 'w')
    try:
        from paddleocr import PaddleOCR
        PADDLE_SUPPORT = True
    finally:
        sys.stderr = stderr_backup
except ImportError:
    PADDLE_SUPPORT = False

try:
    from skimage.metrics import structural_similarity as ssim
    SSIM_SUPPORT = True
except ImportError:
    SSIM_SUPPORT = False

try:
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.lib.utils import ImageReader
    REPORTLAB_SUPPORT = True
except ImportError:
    REPORTLAB_SUPPORT = False


class ScrollableImageFrame(tk.Frame):
    """Kaydırma çubukları olan bir resim görüntüleme çerçevesi."""
    def __init__(self, parent, *args, **kwargs):
        super().__init__(parent, *args, **kwargs)
        
        self.canvas = tk.Canvas(self, bg="#2b2b2b", highlightthickness=0)
        self.v_scroll = tk.Scrollbar(self, orient=tk.VERTICAL, command=self.canvas.yview)
        self.h_scroll = tk.Scrollbar(self, orient=tk.HORIZONTAL, command=self.canvas.xview)
        
        self.canvas.configure(yscrollcommand=self.v_scroll.set, xscrollcommand=self.h_scroll.set)
        
        self.v_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.h_scroll.pack(side=tk.BOTTOM, fill=tk.X)
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.image_item = None
        self.pil_image = None
        self.tk_image = None
        self.zoom_scale = 1.0

        # Mouse wheel ile zoom/pan
        self.canvas.bind("<MouseWheel>", self._on_mousewheel)
        self.canvas.bind("<Control-MouseWheel>", self._on_zoom)

    def show_image(self, pil_image):
        self.pil_image = pil_image
        self.zoom_scale = 1.0
        self._update_image()

    def _update_image(self):
        if not self.pil_image:
            return
        
        w, h = self.pil_image.size
        new_w = int(w * self.zoom_scale)
        new_h = int(h * self.zoom_scale)
        
        resized = self.pil_image.resize((new_w, new_h), Image.Resampling.LANCZOS)
        self.tk_image = ImageTk.PhotoImage(resized)
        
        if self.image_item:
            self.canvas.delete(self.image_item)
        
        self.image_item = self.canvas.create_image(0, 0, anchor=tk.NW, image=self.tk_image)
        self.canvas.config(scrollregion=(0, 0, new_w, new_h))

    def _on_mousewheel(self, event):
        if event.state & 0x0004: # Ctrl key
            self._on_zoom(event)
        else:
            self.canvas.yview_scroll(int(-1*(event.delta/120)), "units")

    def _on_zoom(self, event):
        if event.delta > 0:
            self.zoom_scale *= 1.1
        else:
            self.zoom_scale /= 1.1
        self._update_image()
        
    def set_zoom(self, scale):
        """Dışarıdan zoom seviyesini ayarla."""
        self.zoom_scale = scale
        self._update_image()


class FilePanel(tk.Frame):
    """Dosya seçimi ve önizlemesi yapan panel (Sol/Sağ)."""
    def __init__(self, parent, title="Dosya"):
        super().__init__(parent, bg="#1e1e1e", padx=5, pady=5)
        
        # Başlık ve Dosya Adı
        header_frame = tk.Frame(self, bg="#1e1e1e")
        header_frame.pack(fill=tk.X, pady=(0, 5))

        tk.Label(
            header_frame, text=title, font=("Segoe UI", 10, "bold"),
            bg="#1e1e1e", fg="#bbbbbb"
        ).pack(side=tk.LEFT)

        # Butonlar ve Dosya Adı için sağ frame
        right_header = tk.Frame(header_frame, bg="#1e1e1e")
        right_header.pack(side=tk.RIGHT)

        tk.Button(
            right_header, text="⟲", font=("Segoe UI", 10), 
            bg="#333333", fg="white", bd=0, padx=8, cursor="hand2",
            command=self.rotate_left
        ).pack(side=tk.LEFT, padx=2)

        tk.Button(
            right_header, text="⟳", font=("Segoe UI", 10), 
            bg="#333333", fg="white", bd=0, padx=8, cursor="hand2",
            command=self.rotate_right
        ).pack(side=tk.LEFT, padx=2)

        self.file_label = tk.Label(
            right_header, text="Dosya seçilmedi", font=("Segoe UI", 9, "italic"),
            bg="#1e1e1e", fg="#666666", width=20, anchor="e"
        )
        self.file_label.pack(side=tk.LEFT, padx=5)

        # Görsel Alanı
        self.preview_frame = tk.Frame(self, bg="#2b2b2b", bd=1, relief=tk.SUNKEN)
        self.preview_frame.pack(fill=tk.BOTH, expand=True)
        
        self.canvas = tk.Canvas(self.preview_frame, bg="#2b2b2b", highlightthickness=0, cursor="arrow")
        self.canvas.pack(fill=tk.BOTH, expand=True)
        
        # Bind events
        self.canvas.bind("<ButtonPress-1>", self._on_mouse_down)
        self.canvas.bind("<B1-Motion>", self._on_mouse_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_mouse_up)

        self.file_path = None
        self.current_image = None # Görüntülenen sayfa (PIL) - Rotasyon uygulanmış
        self.original_image = None # Orijinal ham görsel (sadece resim dosyaları için)
        self.doc = None           # PDF ise fitz document
        self.total_pages = 0
        self.current_page_idx = 0
        self.rotation = 0 # 0, 90, 180, 270
        self.diffs = [] # (x, y, w, h) list
        
        # ROI Selection vars
        self.selection_active = False
        self.start_x = None
        self.start_y = None
        self.rect_id = None
        self.selection_coords = None # (x1, y1, x2, y2) on original image



        
    def _update_label_with_page_count(self):
        filename = os.path.basename(self.file_path)
        if len(filename) > 20: filename = filename[:17] + "..."
        
        if self.total_pages > 1:
            self.file_label.config(text=f"{filename} ({self.total_pages} Sayfa)", fg="#4fc3f7")
        else:
            self.file_label.config(text=filename, fg="#4fc3f7")
            
    def load_file(self, path):
        self.file_path = path
        # Initial label set
        filename = os.path.basename(path)
        if len(filename) > 20: filename = filename[:17] + "..."
        self.file_label.config(text=filename, fg="#4fc3f7")

        ext = path.lower().split('.')[-1]
        self.rotation = 0 # Yeni dosya yüklendiğinde rotasyonu sıfırla
        
        try:
            if ext == "pdf":
                self.doc = fitz.open(path)
                self.original_image = None
                self.total_pages = len(self.doc)
                self.current_page_idx = 0
                self._render_pdf_page(0)
            else:
                self.doc = None
                self.total_pages = 1
                self.current_page_idx = 0
                # Orijinal resmi sakla
                img = Image.open(path)
                self.original_image = img
                self.current_image = img.copy() # Rotasyon yok
                self._show_image(self.current_image)
            
            self._update_label_with_page_count()
                
        except Exception as e:
            messagebox.showerror("Hata", f"Dosya yüklenemedi:\n{e}")

    def _render_pdf_page(self, page_idx):
        if not self.doc: return
        page = self.doc.load_page(page_idx)
        # 3x zoom (önceki adımdaki değişiklik korunuyor)
        pix = page.get_pixmap(matrix=fitz.Matrix(3, 3)) 
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        
        # Rotasyon uygula (varsa)
        if self.rotation != 0:
            img = img.rotate(-self.rotation, expand=True) # expand=True ile kırpmaz
            
        self.current_image = img
        self._show_image(img)

    def _show_image(self, pil_img):
        # Canvas boyutuna göre resize et (aspect ratio koruyarak)
        self.update_idletasks() # Boyutları güncelle
        cw = self.canvas.winfo_width()
        ch = self.canvas.winfo_height()
        
        if cw < 10 or ch < 10: cw, ch = 300, 400

        w, h = pil_img.size
        ratio = min(cw/w, ch/h)
        new_w, new_h = int(w*ratio), int(h*ratio)
        
        # Store for coordinate conversion
        self.disp_ratio = ratio
        self.disp_offset = ((cw - new_w) // 2, (ch - new_h) // 2)
        
        img_resized = pil_img.resize((new_w, new_h), Image.Resampling.LANCZOS)
        self.tk_img = ImageTk.PhotoImage(img_resized)
        
        self.canvas.delete("all")
        # Merkeze yerleştir
        x_off, y_off = self.disp_offset
        self.canvas.create_image(x_off, y_off, anchor=tk.NW, image=self.tk_img)

        # Fark kutularını çiz (varsa)
        if hasattr(self, 'diffs') and self.diffs:
            # Scale factor: new_w / original_w
            orig_w, orig_h = pil_img.size
            scale = new_w / orig_w
            
            for idx, (dx, dy, dw, dh) in enumerate(self.diffs):
                # Scale coordinates
                rx = x_off + dx * scale
                ry = y_off + dy * scale
                rw = dw * scale
                rh = dh * scale
                
                # Draw box
                self.canvas.create_rectangle(rx, ry, rx+rw, ry+rh, outline="red", width=2)
                
                # Draw number background and text
                self.canvas.create_rectangle(rx, ry-12, rx+15, ry, fill="red", outline="")
                self.canvas.create_text(rx+7, ry-6, text=str(idx+1), fill="white", font=("Segoe UI", 8, "bold"))
                
        # Mevcut seçimi tekrar çiz (varsa)
        if self.selection_coords:
             sx1, sy1, sx2, sy2 = self.selection_coords
             # Convert back to display coords
             dx1 = x_off + sx1 * ratio
             dy1 = y_off + sy1 * ratio
             dx2 = x_off + sx2 * ratio
             dy2 = y_off + sy2 * ratio
             self.rect_id = self.canvas.create_rectangle(dx1, dy1, dx2, dy2, outline="#00ff00", width=2, dash=(5, 2))
    
    def show_diffs(self, pil_img, diffs):
        """Farkları görsel üzerine işaretle ve göster."""
        # Not: pil_img normalize edilmiş görsel olmalı
        self.current_image = pil_img
        self.diffs = diffs
        self._show_image(pil_img)

    def clear_diffs(self):
        self.diffs = []
        # Resmi refresh et (orijinal veya current duruma göre)
        if self.current_image:
            self._show_image(self.current_image)

    def enable_selection(self):
        self.selection_active = True
        self.canvas.config(cursor="cross")
        
    def disable_selection(self):
        self.selection_active = False
        self.canvas.config(cursor="arrow")
        
    def clear_selection(self):
        self.selection_coords = None
        if self.rect_id:
            self.canvas.delete(self.rect_id)
            self.rect_id = None
        # Refresh to clear drawing if needed logic overlaps
        if self.current_image:
             self._show_image(self.current_image)

    def _on_mouse_down(self, event):
        if not self.selection_active or not self.current_image: return
        self.start_x = event.x
        self.start_y = event.y
        if self.rect_id:
            self.canvas.delete(self.rect_id)
            self.rect_id = None
            self.selection_coords = None

    def _on_mouse_drag(self, event):
        if not self.selection_active or not self.start_x: return
        cur_x, cur_y = event.x, event.y
        
        if self.rect_id:
            self.canvas.coords(self.rect_id, self.start_x, self.start_y, cur_x, cur_y)
        else:
            self.rect_id = self.canvas.create_rectangle(self.start_x, self.start_y, cur_x, cur_y, outline="#00ff00", width=2, dash=(5, 2))

    def _on_mouse_up(self, event):
        if not self.selection_active or not self.start_x: return
        end_x, end_y = event.x, event.y
        
        # Normalize coordinates
        x1, y1 = min(self.start_x, end_x), min(self.start_y, end_y)
        x2, y2 = max(self.start_x, end_x), max(self.start_y, end_y)
        
        # Convert to image coordinates
        if hasattr(self, 'disp_offset') and hasattr(self, 'disp_ratio') and self.disp_ratio > 0:
             off_x, off_y = self.disp_offset
             
             # Relative to image drawing area
             eff_x1 = max(0, x1 - off_x)
             eff_y1 = max(0, y1 - off_y)
             eff_x2 = max(0, x2 - off_x)
             eff_y2 = max(0, y2 - off_y)
             
             # Convert to original image scale
             orig_x1 = int(eff_x1 / self.disp_ratio)
             orig_y1 = int(eff_y1 / self.disp_ratio)
             orig_x2 = int(eff_x2 / self.disp_ratio)
             orig_y2 = int(eff_y2 / self.disp_ratio)
             
             w, h = self.current_image.size
             # Clamp
             orig_x1 = max(0, min(w, orig_x1))
             orig_y1 = max(0, min(h, orig_y1))
             orig_x2 = max(0, min(w, orig_x2))
             orig_y2 = max(0, min(h, orig_y2))
             
             if abs(orig_x2 - orig_x1) > 10 and abs(orig_y2 - orig_y1) > 10:
                 self.selection_coords = (orig_x1, orig_y1, orig_x2, orig_y2)
             else:
                 # Too small
                 if self.rect_id: self.canvas.delete(self.rect_id)
                 self.rect_id = None
        
        self.start_x = None
        self.start_y = None
        
    def get_selection_image(self):
        """Varsa seçili alanı crop edip döndürür, yoksa tüm resmi."""
        if not self.current_image: return None
        
        if self.selection_coords:
            return self.current_image.crop(self.selection_coords)
        return self.current_image

    
    def get_page_image(self, page_idx):
        """Belirtilen sayfanın PIL görselini döndürür (Rotasyon uygulanmış)."""
        if not self.file_path: return None

        img = None
        if self.doc: # PDF
            if 0 <= page_idx < self.total_pages:
                page = self.doc.load_page(page_idx)
                # Yüksek çözünürlüklü render (OCR için önemli)
                pix = page.get_pixmap(matrix=fitz.Matrix(3, 3)) 
                img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        else: # Resim dosyası
            if page_idx == 0 and self.original_image:
                img = self.original_image.copy()

        if img and self.rotation != 0:
            img = img.rotate(-self.rotation, expand=True)
            
        return img

    def rotate_left(self):
        """Saat yönünün tersine 90 derece döndür."""
        if not self.file_path: return
        self.rotation = (self.rotation - 90) % 360
        self._refresh_view()

    def rotate_right(self):
        """Saat yönünde 90 derece döndür."""
        if not self.file_path: return
        self.rotation = (self.rotation + 90) % 360
        self._refresh_view()

    def _refresh_view(self):
        """Mevcut görünümü rotasyona göre güncelle."""
        if self.doc:
            self._render_pdf_page(self.current_page_idx)
        elif self.original_image:
            # Orijinalden tekrar oluştur
            self.current_image = self.original_image.rotate(-self.rotation, expand=True)
            self._show_image(self.current_image)

    def get_total_pages(self):
        return self.total_pages


class DiffResultWindow(tk.Frame):
    """Karşılaştırma sonuçlarını ve detaylarını gösteren pencere (Ana ekrana gömülü)."""
    def __init__(self, parent, page_results, on_back=None):
        super().__init__(parent)
        self.on_back = on_back
        self.bg_color = "#1e1e1e"
        self.configure(bg=self.bg_color)
        
        self.page_results = page_results
        self.current_page_idx = 0

        # --- Sidebar (Sayfa Listesi) ---
        sidebar = tk.Frame(self, bg="#252526", width=200)
        sidebar.pack(side=tk.LEFT, fill=tk.Y)
        sidebar.pack_propagate(False)

        # Geri Butonu
        tk.Button(
            sidebar, text="← Geri Dön", font=("Segoe UI", 10, "bold"),
            bg="#444444", fg="white", relief=tk.FLAT, padx=10, pady=5,
            cursor="hand2", command=self.go_back
        ).pack(fill=tk.X, padx=10, pady=10)

        tk.Label(
            sidebar, text="SAYFALAR", font=("Segoe UI", 12, "bold"),
            bg="#252526", fg="#cccccc", pady=10
        ).pack(fill=tk.X)

        self.page_listbox = tk.Listbox(
            sidebar, bg="#1e1e1e", fg="#dddddd", font=("Segoe UI", 11),
            selectbackground="#0078d4", selectforeground="white",
            relief=tk.FLAT, bd=0, highlightthickness=0
        )
        self.page_listbox.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.page_listbox.bind("<<ListboxSelect>>", self._on_page_select)

        # Sayfaları listeye ekle
        for res in page_results:
            p_num = res["page_num"]
            diff_count = len(res["differences"])
            self.page_listbox.insert(tk.END, f"Sayfa {p_num} ({diff_count} fark)")
        
        # --- Ana İçerik ---
        self.main_area = tk.Frame(self, bg=self.bg_color)
        self.main_area.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

        # Üst Panel (Özet)
        self.summary_frame = tk.Frame(self.main_area, bg="#252526", pady=10, padx=15)
        self.summary_frame.pack(fill=tk.X)
        
        # (Özet etiketleri burada dinamik oluşturulacak)
        
        # Notebook (Sekmeler)
        self.notebook = ttk.Notebook(self.main_area)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Stil
        style = ttk.Style()
        style.theme_use('default')
        style.configure("TNotebook", background=self.bg_color, borderwidth=0)
        style.configure("TNotebook.Tab", background="#333333", foreground="#eeeeee", padding=[15, 5], font=("Segoe UI", 10))
        style.map("TNotebook.Tab", background=[("selected", "#0078d4")], foreground=[("selected", "#ffffff")])

        # İlk sayfayı seç
        self.page_listbox.select_set(0)
        self._load_page_result(0)

        # Alt Panel (Export)
        btn_frame = tk.Frame(self.main_area, bg=self.bg_color, pady=10)
        btn_frame.pack(fill=tk.X, side=tk.BOTTOM)

        tk.Button(
            btn_frame, text="📥 PDF Raporu İndir",
            font=("Segoe UI", 11, "bold"), bg="#28a745", fg="white",
            relief=tk.FLAT, padx=20, pady=8, cursor="hand2",
            command=self._export_pdf
        ).pack(side=tk.RIGHT, padx=20)

    def go_back(self):
        if self.on_back:
            self.on_back()

    def _on_page_select(self, event):
        selection = self.page_listbox.curselection()
        if selection:
            idx = selection[0]
            self._load_page_result(idx)

    def _load_page_result(self, idx):
        self.current_page_idx = idx
        result = self.page_results[idx]
        
        # 1. Özeti güncelle
        for widget in self.summary_frame.winfo_children():
            widget.destroy()
        self._build_page_summary(self.summary_frame, result)

        # 2. Sekmeleri temizle ve yeniden oluştur
        for tab in self.notebook.tabs():
            self.notebook.forget(tab)
        
        self._build_visual_tab(self.notebook, result)
        self._build_text_tab(self.notebook, result["text_result"])
        self._build_ssim_tab(self.notebook, result["ssim_result"])
        self._build_color_tab(self.notebook, result["color_result"])
        self._build_feature_tab(self.notebook, result["feature_result"])
        self._build_feature_tab(self.notebook, result["feature_result"])

    def _build_page_summary(self, parent, result):
        diff_count = len(result["differences"])
        
        tk.Label(
            parent, text=f"Sayfa {result['page_num']} Özeti", 
            font=("Segoe UI", 16, "bold"), bg="#252526", fg="white"
        ).pack(anchor=tk.W)

        stats_frame = tk.Frame(parent, bg="#252526")
        stats_frame.pack(anchor=tk.W, pady=5)

        def add_stat(label, value, color="#cccccc"):
            f = tk.Frame(stats_frame, bg="#333333", padx=10, pady=5)
            f.pack(side=tk.LEFT, padx=5)
            tk.Label(f, text=label, font=("Segoe UI", 9), bg="#333333", fg="#aaaaaa").pack(anchor=tk.W)
            tk.Label(f, text=str(value), font=("Segoe UI", 11, "bold"), bg="#333333", fg=color).pack(anchor=tk.W)

        add_stat("Görsel Fark", f"{diff_count} Bölge", "#ff6b6b" if diff_count > 0 else "#4caf50")
        
        ssim_score = result["ssim_result"].get("score", 0) if result["ssim_result"] else 0
        add_stat("SSIM (Yapısal)", f"%{ssim_score*100:.1f}", "#4caf50" if ssim_score > 0.9 else "#ff9800")

        ocr_ratio = result["text_result"].get("ratio")
        add_stat("Metin Benzerliği", f"%{ocr_ratio*100:.1f}", "#4caf50" if ocr_ratio and ocr_ratio > 0.9 else "#ff9800")

    def _build_visual_tab(self, notebook, result):
        """Görsel farkları gösteren sekme (Yan yana Master/Print)."""
        tab = tk.Frame(notebook, bg="#2b2b2b")
        notebook.add(tab, text="  Görsel Farklar  ")
        
        # Split view container
        paned = tk.Frame(tab, bg="#2b2b2b")
        paned.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Grid layout for side-by-side
        paned.columnconfigure(0, weight=1)
        paned.columnconfigure(1, weight=1)
        paned.rowconfigure(1, weight=1) # 0 is label, 1 is image

        # Left (Master) with boxes
        lbl1 = tk.Label(paned, text="Master (Sol)", fg="#4fc3f7", bg="#2b2b2b", font=("Segoe UI", 11, "bold"))
        lbl1.grid(row=0, column=0, pady=(0, 5))
        
        viewer1 = ScrollableImageFrame(paned, bg="#2b2b2b")
        viewer1.grid(row=1, column=0, sticky="nsew", padx=(0, 5))
        
        # Right (Print) with boxes
        lbl2 = tk.Label(paned, text="Print (Sağ)", fg="#4fc3f7", bg="#2b2b2b", font=("Segoe UI", 11, "bold"))
        lbl2.grid(row=0, column=1, pady=(0, 5))

        viewer2 = ScrollableImageFrame(paned, bg="#2b2b2b")
        viewer2.grid(row=1, column=1, sticky="nsew", padx=(5, 0))

        # Check data
        img1_n = result.get("img1_norm")
        img2_n = result.get("img2_norm")
        diffs = result.get("differences", [])
        
        if img1_n and img2_n:
            # Draw boxes on copies
            disp1 = img1_n.copy()
            disp2 = img2_n.copy()
            draw1 = ImageDraw.Draw(disp1)
            draw2 = ImageDraw.Draw(disp2)
            
            # Use red rectangle
            for idx, (x, y, w, h) in enumerate(diffs):
                # Box
                draw1.rectangle([x, y, x+w, y+h], outline="red", width=3)
                draw2.rectangle([x, y, x+w, y+h], outline="red", width=3)
                
                # Number badge (top-left)
                # Helper for text background
                t_bbox = draw1.textbbox((x, y), str(idx+1)) # needs font? default is ok
                # Draw small background for number
                draw1.rectangle([x, y-12, x+15, y], fill="red")
                draw2.rectangle([x, y-12, x+15, y], fill="red")
                draw1.text((x+2, y-12), str(idx+1), fill="white")
                draw2.text((x+2, y-12), str(idx+1), fill="white")

            viewer1.show_image(disp1)
            viewer2.show_image(disp2)
        elif result.get("diff_image"):
            # Fallback to old diff image if norm images missing logic
            viewer1.show_image(result["diff_image"])
        else:
            tk.Label(tab, text="Görsel fark verisi yok.", bg="#2b2b2b", fg="white").pack()
            
        # --- Independent Zoom Sliders ---
        # Row 2 for sliders
        
        # Slider 1 (Left/Master)
        frame_z1 = tk.Frame(paned, bg="#2b2b2b")
        frame_z1.grid(row=2, column=0, sticky="ew", padx=10, pady=5)
        
        tk.Label(frame_z1, text="Zoom:", bg="#2b2b2b", fg="#aaaaaa", font=("Segoe UI", 9)).pack(side=tk.LEFT)
        scale1 = tk.Scale(
            frame_z1, from_=0.1, to=3.0, resolution=0.1, orient=tk.HORIZONTAL,
            bg="#333333", fg="white", highlightthickness=0, bd=0, troughcolor="#2b2b2b",
            activebackground="#0078d4", command=lambda v: viewer1.set_zoom(float(v))
        )
        scale1.set(1.0)
        scale1.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)

        # Slider 2 (Right/Print)
        frame_z2 = tk.Frame(paned, bg="#2b2b2b")
        frame_z2.grid(row=2, column=1, sticky="ew", padx=10, pady=5)
        
        tk.Label(frame_z2, text="Zoom:", bg="#2b2b2b", fg="#aaaaaa", font=("Segoe UI", 9)).pack(side=tk.LEFT)
        scale2 = tk.Scale(
            frame_z2, from_=0.1, to=3.0, resolution=0.1, orient=tk.HORIZONTAL,
            bg="#333333", fg="white", highlightthickness=0, bd=0, troughcolor="#2b2b2b",
            activebackground="#0078d4", command=lambda v: viewer2.set_zoom(float(v))
        )
        scale2.set(1.0)
        scale2.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)

    def _build_text_tab(self, notebook, text_result):
        """Metin karşılaştırma sekmesi."""
        try:
            with open("debug_log.txt", "a") as f:
                f.write("Building text tab...\n")
        except: pass

        tab = tk.Frame(notebook, bg="#2b2b2b")
        notebook.add(tab, text="  Metin Karsilastirma  ")
        
        ratio = text_result.get("ratio")
        diff_text = text_result.get("diff_text")
        # diff_text not used for side-by-side but we have t1, t2
        
        error = text_result.get("error")

        # Başlık ve Skor
        header = tk.Frame(tab, bg="#2b2b2b")
        header.pack(fill=tk.X, padx=10, pady=10)

        color = "#4caf50" if ratio and ratio >= 0.9 else "#ff9800" if ratio and ratio >= 0.7 else "#f44336"
        
        if ratio is not None:
            tk.Label(
                header,
                text=f"Metin Benzerligi: %{ratio * 100:.1f}",
                font=("Segoe UI", 16, "bold"),
                bg="#2b2b2b", fg=color
            ).pack(side=tk.LEFT)

        if error:
            tk.Label(
                header, text=f"  ({error})",
                font=("Segoe UI", 10), bg="#2b2b2b", fg="#ff9800"
            ).pack(side=tk.LEFT, padx=(10, 0))

        # Metinler yan yana
        texts_frame = tk.Frame(tab, bg="#2b2b2b")
        texts_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        # Sol metin
        left_frame = tk.Frame(texts_frame, bg="#2b2b2b")
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 5))

        tk.Label(
            left_frame, text="Master Metni:",
            font=("Segoe UI", 10, "bold"), bg="#2b2b2b", fg="#4fc3f7"
        ).pack(anchor=tk.W)

        left_text = tk.Text(
            left_frame, font=("Consolas", 10), bg="#1e1e1e", fg="#dddddd",
            wrap=tk.WORD, relief=tk.FLAT, padx=8, pady=8
        )
        left_text.pack(fill=tk.BOTH, expand=True)

        # Sağ metin
        right_frame = tk.Frame(texts_frame, bg="#2b2b2b")
        right_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(5, 0))

        tk.Label(
            right_frame, text="Print Metni:",
            font=("Segoe UI", 10, "bold"), bg="#2b2b2b", fg="#4fc3f7"
        ).pack(anchor=tk.W)

        right_text = tk.Text(
            right_frame, font=("Consolas", 10), bg="#1e1e1e", fg="#dddddd",
            wrap=tk.WORD, relief=tk.FLAT, padx=8, pady=8
        )
        right_text.pack(fill=tk.BOTH, expand=True)

        # Metinleri yan yana karakter bazlı farklarla göster
        t1 = text_result.get("text1") or ""
        t2 = text_result.get("text2") or ""

        # Karakter bazlı SequenceMatcher
        matcher = difflib.SequenceMatcher(None, t1, t2)
        
        # Tag konfigürasyonu - Daha belirgin "marker" stili
        left_text.tag_configure("removed", background="#ff6b6b", foreground="white")
        right_text.tag_configure("added", background="#4caf50", foreground="white")

        # Master (Sol) ve Print (Sağ) metinlerini opcodelara göre doldur
        try:
            # HACK: Force initialize opcodes if missing (bug fix for weird environment)
            if not hasattr(matcher, 'opcodes'):
                 matcher.opcodes = None
            
            opcodes = matcher.get_opcodes()
            
            for tag, i1, i2, j1, j2 in opcodes:
                if tag == 'equal':
                    left_text.insert(tk.END, t1[i1:i2])
                    right_text.insert(tk.END, t2[j1:j2])
                elif tag == 'delete':
                    left_text.insert(tk.END, t1[i1:i2], "removed")
                elif tag == 'insert':
                    right_text.insert(tk.END, t2[j1:j2], "added")
                elif tag == 'replace':
                    left_text.insert(tk.END, t1[i1:i2], "removed")
                    right_text.insert(tk.END, t2[j1:j2], "added")
        except AttributeError as e:
            # Fallback if SequenceMatcher fails completely
            left_text.insert(tk.END, t1)
            right_text.insert(tk.END, t2)
            error_msg = f"Diff error: {e}"
            print(error_msg)
            with open("debug_log.txt", "a") as f:
                f.write(f"ERROR: {error_msg}\n")
                import sys
                f.write(f"Python: {sys.version}\n")
                f.write(f"Matcher dir: {dir(matcher)}\n")

        left_text.config(state=tk.DISABLED)
        right_text.config(state=tk.DISABLED)

        # Fark çıktısı
        diff_text_val = text_result.get("diff_text", "")
        if diff_text_val:
            diff_frame = tk.Frame(tab, bg="#2b2b2b")
            diff_frame.pack(fill=tk.BOTH, padx=10, pady=(5, 10))

            tk.Label(
                diff_frame, text="Farklar (Diff):",
                font=("Segoe UI", 10, "bold"), bg="#2b2b2b", fg="#ff6b6b"
            ).pack(anchor=tk.W)

            diff_widget = tk.Text(
                diff_frame, font=("Consolas", 9), bg="#1a1a2e", fg="#dddddd",
                wrap=tk.WORD, relief=tk.FLAT, padx=8, pady=8, height=8
            )
            diff_widget.pack(fill=tk.BOTH)

            # Renklendirme tag'leri
            diff_widget.tag_configure("added", foreground="#4caf50")
            diff_widget.tag_configure("removed", foreground="#f44336")
            diff_widget.tag_configure("header", foreground="#64b5f6")

            for line in diff_text_val.split("\n"):
                if line.startswith("+++") or line.startswith("---") or line.startswith("@@"):
                    diff_widget.insert(tk.END, line + "\n", "header")
                elif line.startswith("+"):
                    diff_widget.insert(tk.END, line + "\n", "added")
                elif line.startswith("-"):
                    diff_widget.insert(tk.END, line + "\n", "removed")
                else:
                    diff_widget.insert(tk.END, line + "\n")

            diff_widget.config(state=tk.DISABLED)

    def _build_ssim_tab(self, notebook, ssim_result):
        """Yapısal Benzerlik (SSIM) sekmesi."""
        tab = tk.Frame(notebook, bg="#2b2b2b")
        notebook.add(tab, text="  Yapisal Benzerlik  ")

        score = ssim_result.get("score")
        diff_image = ssim_result.get("diff_image")

        if score is None:
            tk.Label(
                tab, text="SSIM hesaplanamadi.\nscikit-image yukleyin: pip install scikit-image",
                font=("Segoe UI", 12), bg="#2b2b2b", fg="#ff9800"
            ).pack(expand=True)
            return

        # Skor gösterimi
        header = tk.Frame(tab, bg="#2b2b2b")
        header.pack(fill=tk.X, padx=10, pady=10)

        color = "#4caf50" if score >= 0.8 else "#ff9800" if score >= 0.5 else "#f44336"
        tk.Label(
            header,
            text=f"SSIM Skoru: %{score * 100:.1f}",
            font=("Segoe UI", 20, "bold"),
            bg="#2b2b2b", fg=color
        ).pack(side=tk.LEFT)

        desc = ""
        if score >= 0.95:
            desc = "(Neredeyse ayni)"
        elif score >= 0.8:
            desc = "(Cok benzer)"
        elif score >= 0.5:
            desc = "(Kismen benzer)"
        else:
            desc = "(Farkli)"

        tk.Label(
            header, text=f"  {desc}",
            font=("Segoe UI", 14), bg="#2b2b2b", fg="#aaaaaa"
        ).pack(side=tk.LEFT)

        # SSIM fark haritası
        if diff_image:
            tk.Label(
                tab, text="Fark Haritasi (sicak renkler = fark bolgesi):",
                font=("Segoe UI", 10), bg="#2b2b2b", fg="#cccccc"
            ).pack(anchor=tk.W, padx=10)

            viewer = ScrollableImageFrame(tab, bg="#2b2b2b")
            viewer.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))
            viewer.show_image(diff_image)

    def _build_color_tab(self, notebook, color_result):
        """Renk karşılaştırma sekmesi."""
        tab = tk.Frame(notebook, bg="#2b2b2b")
        notebook.add(tab, text="  Renk Karsilastirma  ")

        overall = color_result.get("overall")
        channels = color_result.get("channels", {})

        if overall is None:
            tk.Label(
                tab, text="Renk karsilastirmasi yapilamadi.",
                font=("Segoe UI", 12), bg="#2b2b2b", fg="#ff9800"
            ).pack(expand=True)
            return

        # Genel skor
        color = "#4caf50" if overall >= 0.8 else "#ff9800" if overall >= 0.5 else "#f44336"
        tk.Label(
            tab,
            text=f"Genel Renk Benzerligi: %{overall * 100:.1f}",
            font=("Segoe UI", 18, "bold"),
            bg="#2b2b2b", fg=color
        ).pack(pady=(20, 10))

        # Kanal detayları
        detail_frame = tk.Frame(tab, bg="#2b2b2b")
        detail_frame.pack(pady=10)

        channel_colors = {
            "Kirmizi (R)": "#f44336",
            "Yesil (G)": "#4caf50",
            "Mavi (B)": "#2196f3"
        }

        for channel, score in channels.items():
            c_name = channel_colors.get(channel, "#cccccc")
            f = tk.Frame(detail_frame, bg="#333333", padx=10, pady=5)
            f.pack(side=tk.LEFT, padx=10)
            
            tk.Label(f, text=channel, font=("Segoe UI", 12), bg="#333333", fg="white").pack()
            tk.Label(
                f, text=f"%{score * 100:.1f}",
                font=("Segoe UI", 14, "bold"), bg="#333333", fg=c_name
            ).pack()

    def _build_feature_tab(self, notebook, feature_result):
        """Feature Matching (ORB) sekmesi."""
        tab = tk.Frame(notebook, bg="#2b2b2b")
        notebook.add(tab, text="  Feature Matching  ")
        
        if not feature_result:
            tk.Label(tab, text="Feature matching yapilamadi.", bg="#2b2b2b", fg="white").pack()
            return

        score = feature_result.get("score", 0)
        match_image = feature_result.get("match_image")

        header = tk.Frame(tab, bg="#2b2b2b")
        header.pack(fill=tk.X, padx=10, pady=10)

        color = "#4caf50" if score > 0.5 else "#f44336"
        tk.Label(
            header, 
            text=f"Feature Match Skoru: {score:.2f} / 1.0",
            font=("Segoe UI", 14, "bold"), bg="#2b2b2b", fg=color
        ).pack(side=tk.LEFT)

        stats = f"(Total Keypoints: {feature_result.get('total_kp1')} vs {feature_result.get('total_kp2')}, Good Matches: {feature_result.get('good_matches')})"
        tk.Label(
            header, text=stats, 
            font=("Segoe UI", 10), bg="#2b2b2b", fg="#aaaaaa"
        ).pack(side=tk.LEFT, padx=10)

        if match_image:
            viewer = ScrollableImageFrame(tab, bg="#2b2b2b")
            viewer.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))
            viewer.show_image(match_image)


            
    def _export_pdf(self):
        """Tüm sayfaların karşılaştırma sonuçlarını PDF olarak dışa aktarır."""
        if not REPORTLAB_SUPPORT:
            messagebox.showerror("Hata", "PDF ihraci icin 'reportlab' kutuphanesi gerekli.")
            return

        file_path = filedialog.asksaveasfilename(
            defaultextension=".pdf",
            filetypes=[("PDF Dosyasi", "*.pdf")],
            title="Raporu Kaydet"
        )
        if not file_path: return

        try:
            c = canvas.Canvas(file_path, pagesize=A4)
            width, height = A4
            
            # Başlık Sayfası
            c.setFont("Helvetica-Bold", 24)
            c.drawString(50, height - 50, "Karsilastirma Raporu")
            
            c.setFont("Helvetica", 12)
            c.drawString(50, height - 80, f"Tarih: {tk.Frame().winfo_toplevel().tk.call('clock', 'format', [tk.Frame().winfo_toplevel().tk.call('clock', 'seconds')], '-format', '%d.%m.%Y %H:%M')}")
            
            c.drawString(50, height - 110, f"Sayfa Sayisi: {len(self.page_results)}")
            
            y = height - 150
            c.drawString(50, y, "Ozet:")
            y -= 20
            
            for i, res in enumerate(self.page_results):
                diff_count = len(res["differences"])
                ssim_score = res["ssim_result"].get("score", 0) if res["ssim_result"] else 0
                ocr_score = res["text_result"].get("ratio") or 0
                
                line = f"Sayfa {res['page_num']}: {diff_count} fark, SSIM: %{ssim_score*100:.1f}, Metin: %{ocr_score*100:.1f}"
                c.drawString(70, y, line)
                y -= 20
                if y < 50:
                    c.showPage()
                    y = height - 50

            c.showPage()

            # Her sayfa için detaylar
            for res in self.page_results:
                p_num = res["page_num"]
                
                # Sayfa Başlığı
                c.setFont("Helvetica-Bold", 16)
                c.drawString(50, height - 50, f"Sayfa {p_num} Detaylari")
                
                # Görsel Farkı Ekle
                diff_img = res["diff_image"]
                if diff_img:
                    # Resmi geçici dosyaya kaydet
                    import tempfile
                    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
                        diff_img.save(tmp.name)
                        tmp_path = tmp.name
                    
                    # Sayfaya ortala
                    img_w, img_h = diff_img.size
                    aspect = img_h / img_w
                    disp_w = 400
                    disp_h = disp_w * aspect
                    
                    if disp_h > 400: # Yükseklik sınırla
                        disp_h = 400
                        disp_w = disp_h / aspect
                    
                    c.drawImage(tmp_path, 100, height - 500, width=disp_w, height=disp_h)
                    os.unlink(tmp_path)
                
                # Metin Farkı
                text_res = res["text_result"]
                # Safe access using .get("ratio")
                t_ratio = text_res.get("ratio") or 0.0
                c.setFont("Helvetica", 10)
                c.drawString(50, height - 520, f"Metin Benzerligi: %{t_ratio*100:.1f}")
                
                # Sadece ilk 5 farkı yazdır (yer kısıtlı)
                diff_text = text_res.get("diff_text") or ""
                lines = diff_text.split('\n')
                y_text = height - 540
                
                valid_lines = [l for l in lines if l.startswith('+') or l.startswith('-')]
                for l in valid_lines[:10]:
                    if l.startswith('+'): c.setFillColorRGB(0, 0.5, 0)
                    elif l.startswith('-'): c.setFillColorRGB(0.8, 0, 0)
                    else: c.setFillColorRGB(0, 0, 0)
                    
                    c.drawString(50, y_text, l[:80]) # Uzun satırları kes
                    y_text -= 12
                
                c.setFillColorRGB(0, 0, 0)
                c.showPage()

            c.save()
            messagebox.showinfo("Basarili", f"Rapor kaydedildi:\n{file_path}")
            webbrowser.open(file_path)

        except Exception as e:
            messagebox.showerror("Hata", f"PDF olusturulurken hata:\n{e}")

class PixelCompareFrame(tk.Frame):
    def __init__(self, parent, on_back=None):
        super().__init__(parent, bg="#121212")
        self.on_back = on_back

        # Header
        self._init_ui()

    def _init_ui(self):
        self.container = tk.Frame(self)
        self.container.pack(fill=tk.BOTH, expand=True)

        self.selection_view = tk.Frame(self.container, bg="#121212")
        self.selection_view.pack(fill=tk.BOTH, expand=True)

        # Üst Header
        header = tk.Frame(self.selection_view, bg="#1f1f1f", height=60, padx=20)
        header.pack(fill=tk.X)
        
        tk.Button(
            header, text="← Ana Sayfa", font=("Segoe UI", 10, "bold"),
            bg="#C0392B", fg="white", relief=tk.FLAT, padx=12, pady=4,
            cursor="hand2", command=self._go_home
        ).pack(side=tk.LEFT, pady=10, padx=(0, 15))
        
        tk.Label(
            header, text="Pixel Compare",
            font=("Segoe UI", 20, "bold"), bg="#1f1f1f", fg="#ffffff"
        ).pack(side=tk.LEFT, pady=10)

        # Kontrol Butonları
        controls = tk.Frame(self.selection_view, bg="#121212", pady=10)
        controls.pack(fill=tk.X, padx=20)

        # Tekil Dosya Seçimi Butonu (Multi-modal)
        self.multi_select_btn = tk.Button(
            controls, text="📁 Dosya Seç", font=("Segoe UI", 11),
            bg="#ffffff", fg="#0078d4", activebackground="#f0f0f0",
            relief=tk.FLAT, padx=15, pady=5, cursor="hand2",
            command=self._select_files_multi
        )
        self.multi_select_btn.pack(side=tk.LEFT, padx=5)

        self.clear_all_btn = tk.Button(
            controls, text="🧹 Tümünü Temizle", font=("Segoe UI", 10),
            bg="#005a9e", fg="white", activebackground="#004a80",
            relief=tk.FLAT, padx=12, pady=5, cursor="hand2",
            command=self._clear_all
        )
        self.clear_all_btn.pack(side=tk.LEFT, padx=5)

        # Ana içerik
        content = tk.Frame(self.selection_view, bg="#121212")
        content.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)

        # Sol panel (Master)
        self.left_panel = FilePanel(content, title="📄 Master")
        self.left_panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Master Selection Controls
        left_controls = tk.Frame(content, bg="#121212")
        left_controls.pack(side=tk.LEFT, fill=tk.Y)
        
        tk.Button(left_controls, text="⛶ Bölge Seç", bg="#333333", fg="white", 
                  command=self.left_panel.enable_selection).pack(fill=tk.X, pady=2)
        tk.Button(left_controls, text="❌ Temizle", bg="#333333", fg="white", 
                  command=self.left_panel.clear_selection).pack(fill=tk.X, pady=2)


        # Orta — Compare butonu
        middle = tk.Frame(content, bg="#121212", width=80)
        middle.pack(side=tk.LEFT, fill=tk.Y, padx=4)
        middle.pack_propagate(False)

        spacer = tk.Frame(middle, bg="#121212")
        spacer.pack(expand=True)

        self.compare_btn = tk.Button(
            middle,
            text="⚡\nCompare",
            font=("Segoe UI", 11, "bold"),
            bg="#ff6b35", fg="white",
            activebackground="#e55a2b", activeforeground="white",
            relief=tk.FLAT, padx=8, pady=16,
            cursor="hand2",
            command=self._compare
        )
        self.compare_btn.pack(pady=4)

        # Swap butonu
        self.swap_btn = tk.Button(
            middle,
            text="⇄\nSwap",
            font=("Segoe UI", 9),
            bg="#555555", fg="white",
            activebackground="#777777",
            relief=tk.FLAT, padx=8, pady=8,
            cursor="hand2",
            command=self._swap_panels
        )
        self.swap_btn.pack(pady=4)

        # Print Selection Controls
        right_controls = tk.Frame(content, bg="#121212")
        right_controls.pack(side=tk.LEFT, fill=tk.Y)
        
        # Use lambda to delay evaluation of self.right_panel until click
        tk.Button(right_controls, text="⛶ Bölge Seç", bg="#333333", fg="white", 
                  command=lambda: self.right_panel.enable_selection()).pack(fill=tk.X, pady=2)
        tk.Button(right_controls, text="❌ Temizle", bg="#333333", fg="white", 
                  command=lambda: self.right_panel.clear_selection()).pack(fill=tk.X, pady=2)

        # Sağ panel (Print)
        self.right_panel = FilePanel(content, title="📄 Print")
        self.right_panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Alt durum çubuğu
        self.status_var = tk.StringVar(value="Karşılaştırmak için her iki panele de dosya yükleyin.")
        status_bar = tk.Label(
            self.selection_view, textvariable=self.status_var,
            font=("Segoe UI", 9), bg="#252525", fg="#888888",
            anchor=tk.W, padx=12, pady=4
        )
        status_bar.pack(fill=tk.X, side=tk.BOTTOM)

    def _select_files_multi(self):
        """Kullanıcının 1 veya 2 dosya seçmesine izin verir."""
        files = filedialog.askopenfilenames(
            title="Dosya Seç (1 veya 2 adet)",
            filetypes=[("Desteklenenler", "*.png;*.jpg;*.jpeg;*.bmp;*.pdf"), ("Tüm Dosyalar", "*.*")]
        )
        if not files: return

        if len(files) == 1:
            # Tek dosya -> Boş olana yükle
            if not self.left_panel.file_path:
                self.left_panel.load_file(files[0])
            elif not self.right_panel.file_path:
                self.right_panel.load_file(files[0])
            else:
                # İkisi de doluysa -> Solu ez (kullanıcı soldan başlar mantığı)
                self.left_panel.load_file(files[0])
        elif len(files) >= 2:
            # İki dosya -> Sırayla yükle
            self.left_panel.load_file(files[0])
            self.right_panel.load_file(files[1])
            if len(files) > 2:
                messagebox.showinfo("Bilgi", "Sadece ilk 2 dosya yüklendi.")
        
        self._update_status()

    def _clear_all(self):
        """Her şeyi temizle."""
        # Panels reset
        for panel in [self.left_panel, self.right_panel]:
            panel.file_path = None
            panel.doc = None
            panel.current_image = None
            panel.file_label.config(text="Dosya seçilmedi", fg="#666666")
            panel.file_label.config(text="Dosya seçilmedi", fg="#666666")
            panel.diffs = []
            panel.canvas.delete("all")
        
        self._update_status()

    def _update_status(self):
        l = bool(self.left_panel.file_path)
        r = bool(self.right_panel.file_path)
        if l and r:
            self.status_var.set("Karşılaştırma hazır. 'Compare' butonuna basın.")
        elif l or r:
            self.status_var.set("Bir dosya daha seçin.")
        else:
            self.status_var.set("Dosya seçilmedi.")

    def _compare(self):
        if not self.left_panel.file_path or not self.right_panel.file_path:
            messagebox.showwarning("Uyarı", "Lütfen iki dosya seçin.")
            return

        self.status_var.set("Karşılaştırılıyor... Lütfen bekleyin.")
        self.compare_btn.config(state=tk.DISABLED, text="Wait...")
        self.update_idletasks()

        try:
            # Sayfa sayılarını kontrol et
            left_pages = self.left_panel.get_total_pages()
            right_pages = self.right_panel.get_total_pages()
            
            total_pages = max(left_pages, right_pages)
            
            page_results = [] # Her sayfa için sonuçları tutacak
            
            for i in range(total_pages):
                # İlgili sayfa görsellerini al (ROI Desteği)
                # Seçim varsa onu kullan, yoksa tam sayfayı
                img1 = self.left_panel.get_selection_image()
                if not img1:
                     img1 = self.left_panel.get_page_image(i)
                     
                img2 = self.right_panel.get_selection_image()
                if not img2:
                     img2 = self.right_panel.get_page_image(i)
                
                if not img1 or not img2:
                    # Sayfa sayısı uyuşmazlığı varsa boş geçebiliriz veya uyarı verebiliriz
                    # Şimdilik devam, olmayan sayfaNone döner
                    continue

                # --- 1. Görsel (Piksel) Karşılaştırma ---
                # --- 1. Görsel (Piksel) Karşılaştırma ---
                diff_image, differences, img1_norm, img2_norm = self._find_visual_differences(img1, img2)

                # --- 2. Metin (OCR) Karşılaştırma ---
                text1 = self._extract_text(img1)
                text2 = self._extract_text(img2)
                
                # _compare_texts artık tüm bilgileri içeren bir sözlük döndürüyor
                text_result = self._compare_texts(text1, text2)

                # --- 3. SSIM ---
                score, ssim_diff = self._compute_ssim(img1, img2)
                ssim_result = {"score": score, "diff_image": ssim_diff}

                # 4. Color
                overall, channels = self._compare_colors(img1, img2)
                color_result = {"overall": overall, "channels": channels}

                # 5. Feature matching
                feature_result = self._feature_matching(img1, img2)

                page_results.append({
                    "page_num": i + 1,
                    "diff_image": diff_image,
                    "differences": differences,
                    "page_num": i + 1,
                    "diff_image": diff_image,
                    "differences": differences,
                    "img1_norm": img1_norm,
                    "img2_norm": img2_norm,
                    "text_result": text_result,
                    "ssim_result": ssim_result,
                    "color_result": color_result,
                    "feature_result": feature_result
                })

            if not page_results:
                messagebox.showwarning("Hata", "Sayfalar render edilemedi.")
                return

            self.status_var.set(f"Karsilastirma tamamlandi. {len(page_results)} sayfa analiz edildi.")
            
            self.status_var.set(f"Karsilastirma tamamlandi. {len(page_results)} sayfa analiz edildi.")
            
            # İlk sayfadaki farkları ana ekrandaki panellere de yansıt
            if page_results:
                first_res = page_results[0]
                # Normalize edilmiş görselleri ve farkları panel'e gönder
                if first_res.get("img1_norm") and first_res.get("img2_norm"):
                     self.left_panel.show_diffs(first_res["img1_norm"], first_res["differences"])
                     self.right_panel.show_diffs(first_res["img2_norm"], first_res["differences"])

            # Sonuçları Ana Ekrada Göster
            self.selection_view.pack_forget()
            self.results_view = DiffResultWindow(self.container, page_results, on_back=self._show_selection)
            self.results_view.pack(fill=tk.BOTH, expand=True)

        except Exception as e:
            import traceback
            traceback.print_exc()
            messagebox.showerror("Hata", f"Karsilastirma basarisiz:\n{e}")
            self.status_var.set(f"Karsilastirma basarisiz: {e}")
        finally:
            self.compare_btn.config(state=tk.NORMAL, text="Compare")

    def _show_selection(self):
        """Sonuç ekranını kapat ve seçim ekranını göster"""
        if hasattr(self, 'results_view'):
            self.results_view.destroy()
        self.selection_view.pack(fill=tk.BOTH, expand=True)

    def _find_visual_differences(self, pil_img1, pil_img2):
        """
        İki görsel arasındaki farkları bulur.
        Döndürür: (fark_görseli: PIL.Image, farklar: [(x, y, w, h), ...])
        """
        # Boyutları farklıysa normalize et (oranı koruyarak aynı boyuta ölçekle)
        img1_n, img2_n = self._normalize_images(pil_img1, pil_img2)

        w = max(img1_n.width, img2_n.width)
        h = max(img1_n.height, img2_n.height)

        canvas1 = Image.new("RGB", (w, h), (255, 255, 255))
        canvas2 = Image.new("RGB", (w, h), (255, 255, 255))
        canvas1.paste(img1_n, (0, 0))
        canvas2.paste(img2_n, (0, 0))

        # PIL → numpy (OpenCV formatı)
        arr1 = np.array(canvas1)
        arr2 = np.array(canvas2)

        # Gri tonlamaya çevir
        gray1 = cv2.cvtColor(arr1, cv2.COLOR_RGB2GRAY)
        gray2 = cv2.cvtColor(arr2, cv2.COLOR_RGB2GRAY)

        # Fark hesapla
        diff = cv2.absdiff(gray1, gray2)

        # Eşikleme (Daha hassas: 30 -> 10)
        _, thresh = cv2.threshold(diff, 10, 255, cv2.THRESH_BINARY)

        # Gürültü temizle (Daha küçük kernel: 5x5 -> 3x3)
        kernel = np.ones((3, 3), np.uint8)
        thresh = cv2.dilate(thresh, kernel, iterations=1)
        thresh = cv2.erode(thresh, kernel, iterations=1)

        # Konturları bul
        contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        # Fark bölgelerini topla
        differences = []
        result_img = arr1.copy()

        for cnt in contours:
            area = cv2.contourArea(cnt)
            if area < 2: continue # Çok küçük gürültüleri atla (sembolleri yakala)
            x, y, bw, bh = cv2.boundingRect(cnt)
            differences.append((x, y, bw, bh))

            # Kırmızı dikdörtgen çerçeve
            cv2.rectangle(result_img, (x, y), (x + bw, y + bh), (200, 0, 0), 1)

            # Daha belirgin yarı saydam kırmızı dolgu (Marker etkisi)
            overlay = result_img.copy()
            cv2.rectangle(overlay, (x, y), (x + bw, y + bh), (255, 0, 0), -1)
            result_img = cv2.addWeighted(overlay, 0.3, result_img, 0.7, 0)

            # Numara yaz (Sadece kutu yeterince büyükse veya kutunun yanına yaz)
            idx = len(differences)
            if bw > 15 and bh > 15:
                cv2.putText(
                    result_img, str(idx),
                    (x + 2, y + 15), cv2.FONT_HERSHEY_SIMPLEX,
                    0.5, (200, 0, 0), 1
                )
            else:
                # Küçük objeler için numara yanına
                cv2.putText(
                    result_img, str(idx),
                    (x + bw + 2, y + bh + 2), cv2.FONT_HERSHEY_SIMPLEX,
                    0.4, (200, 0, 0), 1
                )

        # Büyüklüğe göre sırala (en büyük önce)
        differences.sort(key=lambda d: d[2] * d[3], reverse=True)

        # numpy → PIL
        diff_pil = Image.fromarray(result_img)
        return diff_pil, differences, img1_n, img2_n

    def _normalize_images(self, pil_img1, pil_img2):
        """İki görseli aynı boyuta normalize eder (oranı koruyarak)."""
        w1, h1 = pil_img1.size
        w2, h2 = pil_img2.size
        
        # En büyük genişliği al
        final_w = max(w1, w2)
        # Orantılı yükseklik (img1 için)
        ratio1 = final_w / w1
        h1_new = int(h1 * ratio1)
        img1_res = pil_img1.resize((final_w, h1_new), Image.Resampling.LANCZOS)
        
        # img2 için
        ratio2 = final_w / w2
        h2_new = int(h2 * ratio2)
        img2_res = pil_img2.resize((final_w, h2_new), Image.Resampling.LANCZOS)
        
        return img1_res, img2_res

    def _preprocess_for_ocr(self, pil_image):
        """OCR öncesi görüntü iyileştirme."""
        # PIL -> OpenCV (Gri tonlama)
        img_cv = np.array(pil_image)
        gray = cv2.cvtColor(img_cv, cv2.COLOR_RGB2GRAY)

        # 1. Upscale — küçük görsellerde OCR doğruluğunu artırır
        h, w = gray.shape
        if max(h, w) < 1500:
            scale = 1500 / max(h, w)
            gray = cv2.resize(gray, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)

        # 2. Gürültü azaltma
        gray = cv2.fastNlMeansDenoising(gray, h=10)

        # 3. Kontrast artırma (CLAHE)
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        gray = clahe.apply(gray)

        # 4. Adaptif eşikleme (binarizasyon)
        binary = cv2.adaptiveThreshold(
            gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY, 31, 10
        )

        # 5. Eğrilik düzeltme (deskew)
        coords = np.column_stack(np.where(binary < 128))
        if len(coords) > 100:
            angle = cv2.minAreaRect(coords)[-1]
            if angle < -45:
                angle = -(90 + angle)
            else:
                angle = -angle
            if abs(angle) > 0.5 and abs(angle) < 15:
                (bh, bw) = binary.shape
                center = (bw // 2, bh // 2)
                M = cv2.getRotationMatrix2D(center, angle, 1.0)
                binary = cv2.warpAffine(
                    binary, M, (bw, bh),
                    flags=cv2.INTER_CUBIC,
                    borderMode=cv2.BORDER_REPLICATE
                )

        return Image.fromarray(binary)

    def _extract_text(self, pil_image):
        """OCR ile görselden metin çıkarır. PaddleOCR > Tesseract sırasıyla dener."""
        # Ön-işleme uygula
        processed = self._preprocess_for_ocr(pil_image)

        # Önce PaddleOCR dene (daha yüksek doğruluk)
        if PADDLE_SUPPORT:
            try:
                if not hasattr(self, '_paddle_ocr'):
                    self._paddle_ocr = PaddleOCR(lang="tr", show_log=False)
                arr = np.array(pil_image)  # PaddleOCR orijinal renkli görsel ister
                result = self._paddle_ocr.ocr(arr, cls=True)
                lines = []
                if result and result[0]:
                    for line_info in result[0]:
                        if line_info and len(line_info) >= 2:
                            text_info = line_info[1]
                            if isinstance(text_info, (list, tuple)):
                                lines.append(text_info[0])
                            else:
                                lines.append(str(text_info))
                text = "\n".join(lines).strip()
                if text:
                    return text
            except Exception:
                pass

        # PaddleOCR başarısızsa Tesseract'a düş
        if TESSERACT_SUPPORT:
            try:
                try:
                    text = pytesseract.image_to_string(processed, lang="tur+eng")
                except pytesseract.TesseractError:
                    text = pytesseract.image_to_string(processed, lang="eng")
                return text.strip()
            except Exception:
                pass

        return None

    def _compare_texts(self, text1, text2):
        """İki metin arasındaki benzerliği hesaplar."""
        result = {
            "ratio": 0.0,
            "diff_text": "",
            "error": None,
            "text1": text1,
            "text2": text2
        }

        if not text1 and not text2:
            result["ratio"] = 1.0
            result["diff_text"] = "Metin yok."
            result["error"] = "Her iki dosyada da metin bulunamadi."
            return result

        if not text1 or not text2:
            result["ratio"] = 0.0
            result["error"] = "Dosyalardan birinde metin bulunamadi."
            return result

        # Benzerlik oranı
        ratio = difflib.SequenceMatcher(None, text1, text2).ratio()
        result["ratio"] = ratio

        # Satır bazlı fark
        lines1 = text1.splitlines(keepends=True)
        lines2 = text2.splitlines(keepends=True)
        diff = difflib.unified_diff(
            lines1, lines2,
            fromfile="Sol Dosya", tofile="Sağ Dosya",
            lineterm=""
        )
        diff_text = "".join(diff)
        result["diff_text"] = diff_text

        return result

    def _compute_ssim(self, pil_img1, pil_img2):
        """SSIM (Yapısal Benzerlik) hesaplar."""
        if not SSIM_SUPPORT or not CV2_SUPPORT:
            return None, None

        # Aynı boyuta getir
        img1, img2 = self._normalize_images(pil_img1, pil_img2)

        # Aynı canvas boyutuna yerleştir
        w = max(img1.width, img2.width)
        h = max(img1.height, img2.height)
        canvas1 = Image.new("RGB", (w, h), (255, 255, 255))
        canvas2 = Image.new("RGB", (w, h), (255, 255, 255))
        canvas1.paste(img1, (0, 0))
        canvas2.paste(img2, (0, 0))

        arr1 = np.array(canvas1)
        arr2 = np.array(canvas2)

        gray1 = cv2.cvtColor(arr1, cv2.COLOR_RGB2GRAY)
        gray2 = cv2.cvtColor(arr2, cv2.COLOR_RGB2GRAY)

        score, diff_map = ssim(gray1, gray2, full=True)

        # Fark haritasını görselleştir
        diff_map = (1.0 - diff_map) * 255
        diff_map = diff_map.astype(np.uint8)
        diff_colored = cv2.applyColorMap(diff_map, cv2.COLORMAP_JET)
        diff_colored = cv2.cvtColor(diff_colored, cv2.COLOR_BGR2RGB)
        diff_pil = Image.fromarray(diff_colored)

        return score, diff_pil

    def _compare_colors(self, pil_img1, pil_img2):
        """Renk histogramı karşılaştırması yapar."""
        if not CV2_SUPPORT:
            return None, {}

        arr1 = np.array(pil_img1)
        arr2 = np.array(pil_img2)

        similarities = {}
        channel_names = ["Kırmızı (R)", "Yeşil (G)", "Mavi (B)"]

        for i, name in enumerate(channel_names):
            hist1 = cv2.calcHist([arr1], [i], None, [256], [0, 256])
            hist2 = cv2.calcHist([arr2], [i], None, [256], [0, 256])
            cv2.normalize(hist1, hist1)
            cv2.normalize(hist2, hist2)
            corr = cv2.compareHist(hist1, hist2, cv2.HISTCMP_CORREL)
            similarities[name] = corr

        overall = sum(similarities.values()) / len(similarities)
        return overall, similarities

    def _feature_matching(self, pil_img1, pil_img2):
        """ORB feature matching ile içerik bazlı görsel karşılaştırma."""
        if not CV2_SUPPORT:
            return None

        arr1 = np.array(pil_img1)
        arr2 = np.array(pil_img2)
        gray1 = cv2.cvtColor(arr1, cv2.COLOR_RGB2GRAY)
        gray2 = cv2.cvtColor(arr2, cv2.COLOR_RGB2GRAY)

        # ORB dedektör (fazla özellik bul)
        orb = cv2.ORB_create(nfeatures=2000)
        kp1, des1 = orb.detectAndCompute(gray1, None)
        kp2, des2 = orb.detectAndCompute(gray2, None)

        if des1 is None or des2 is None or len(kp1) < 2 or len(kp2) < 2:
            return {
                "score": 0.0,
                "total_kp1": len(kp1) if kp1 else 0,
                "total_kp2": len(kp2) if kp2 else 0,
                "good_matches": 0,
                "match_image": None,
            }

        # BFMatcher ile eşleştir
        bf = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=False)
        matches = bf.knnMatch(des1, des2, k=2)

        # Lowe's ratio test — iyi eşleşmeleri filtrele
        good_matches = []
        for m_pair in matches:
            if len(m_pair) == 2:
                m, n = m_pair
                if m.distance < 0.75 * n.distance:
                    good_matches.append(m)

        # Skor hesapla
        max_possible = min(len(kp1), len(kp2))
        score = len(good_matches) / max_possible if max_possible > 0 else 0.0
        score = min(score, 1.0)

        # Eşleşme görselini oluştur
        good_matches_sorted = sorted(good_matches, key=lambda x: x.distance)
        match_img = cv2.drawMatches(
            arr1, kp1, arr2, kp2,
            good_matches_sorted[:100],  # En iyi 100 eşleşme
            None, flags=cv2.DrawMatchesFlags_NOT_DRAW_SINGLE_POINTS,
            matchColor=(0, 255, 0),
        )
        match_pil = Image.fromarray(match_img)

        return {
            "score": score,
            "total_kp1": len(kp1),
            "total_kp2": len(kp2),
            "good_matches": len(good_matches),
            "match_image": match_pil
        }



    def _swap_panels(self):
        """Sol ve sağ paneldeki dosyaları yer değiştirir."""
        path1 = self.left_panel.file_path
        path2 = self.right_panel.file_path
        
        # Temizleyip yeniden yükle
        self.left_panel.file_path = None
        self.right_panel.file_path = None
        self.left_panel.file_label.config(text="Dosya seçilmedi", fg="#666666")
        self.right_panel.file_label.config(text="Dosya seçilmedi", fg="#666666")
        self.left_panel.canvas.delete("all")
        self.right_panel.canvas.delete("all")

        if path2: self.left_panel.load_file(path2)
        if path1: self.right_panel.load_file(path1)
    def _go_home(self):
        if self.on_back:
            self.on_back()
