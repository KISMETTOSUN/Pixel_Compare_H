"""
Kutu Tasarım Kontrolü Frame
Prospektüs Kontrolü ile aynı UI yapısı:
  - Kural tablosu (Excel) yükleme
  - Tasarım dosyası (PDF / PNG / JPG) yükleme + ekranda gösterme
  - Analiz başlatma → bulunan alanları canvas üzerinde kırmızı dikdörtgenle işaretleme
"""

from __future__ import annotations

import os
import threading

import customtkinter as ctk
from tkinter import Canvas, filedialog, messagebox, ttk
from PIL import Image, ImageDraw, ImageTk
import openpyxl

from utils.image_analysis_engine import ImageAnalysisEngine


class KutuKontrolFrame(ctk.CTkFrame):
    """Ana pencereden açılan Kutu Tasarım Kontrolü ekranı."""

    def __init__(self, parent, on_back=None):
        super().__init__(parent, fg_color="transparent")
        self.on_back = on_back

        self.engine = ImageAnalysisEngine()
        self.analysis_results: list = []
        self.row_index_to_result: dict = {}

        # Treeview ↔ Excel row mapping
        self.excel_row_to_item_id: dict = {}
        self.item_id_to_excel_row: dict = {}

        # Currently displayed image (PIL) and rendered overlay
        self._base_image: Image.Image | None = None  # original rendered image
        self._orig_image: Image.Image | None = None  # never-rotated original
        self._display_image: ImageTk.PhotoImage | None = None
        self._zoom = 1.0
        self._rotation = 0  # degrees: 0, 90, 180, 270
        self._highlight_rects: list = []       # [{rect, active}] — all found matches
        self._active_rect: list | None = None   # currently clicked rect (brighter)

        # Region selection (canvas coords → image coords)
        self._sel_active = False       # mouse-draw mode on/off
        self._sel_start = None         # (canvas_x, canvas_y)
        self._sel_rect_id = None       # canvas rectangle item id
        self._sel_region = None        # (x0,y0,x1,y1) in IMAGE pixel coords

        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self._build_sidebar()
        self._build_main_area()

    # -----------------------------------------------------------------------
    # Sidebar
    # -----------------------------------------------------------------------

    def _build_sidebar(self):
        self.sidebar = ctk.CTkFrame(self, width=310, corner_radius=0)
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        self.sidebar.grid_propagate(False)
        self.sidebar.grid_rowconfigure(6, weight=1)  # table expands

        # Back button + title
        ctk.CTkButton(
            self.sidebar, text="← Ana Sayfa",
            command=self._go_home,
            fg_color="#C0392B", hover_color="#E74C3C", width=120
        ).grid(row=0, column=0, padx=20, pady=(12, 4), sticky="w")

        ctk.CTkLabel(
            self.sidebar, text="Kutu Tasarım Kontrolü",
            font=ctk.CTkFont(size=15, weight="bold")
        ).grid(row=0, column=0, padx=20, pady=(12, 4), sticky="e")

        # --- Rule table section ---
        rule_header = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        rule_header.grid(row=1, column=0, padx=20, pady=(12, 0), sticky="ew")
        rule_header.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            rule_header, text="1. Kural Tablosu (Excel):",
            font=ctk.CTkFont(size=12, weight="bold"), anchor="w"
        ).grid(row=0, column=0, sticky="w")

        ctk.CTkButton(
            rule_header, text="🔭",
            width=34, height=26,
            font=ctk.CTkFont(size=16),
            fg_color="#2b5f8e", hover_color="#3a7abd",
            command=self._open_rule_detail
        ).grid(row=0, column=1, sticky="e", padx=(4, 0))

        ctk.CTkButton(
            self.sidebar, text="📋  Kural Tablosu Yükle",
            command=self._select_rule_file
        ).grid(row=2, column=0, padx=20, pady=6)

        self.rule_path_label = ctk.CTkLabel(
            self.sidebar, text="Dosya seçilmedi",
            text_color="gray", wraplength=260, anchor="w"
        )
        self.rule_path_label.grid(row=3, column=0, padx=20, pady=(0, 4), sticky="w")

        # Treeview
        table_frame = ctk.CTkFrame(self.sidebar)
        table_frame.grid(row=6, column=0, padx=10, pady=(0, 8), sticky="nsew")
        table_frame.grid_columnconfigure(0, weight=1)
        table_frame.grid_rowconfigure(0, weight=1)

        style = ttk.Style()
        style.theme_use("default")
        style.configure(
            "Kutu.Treeview",
            background="#2b2b2b", foreground="white",
            fieldbackground="#2b2b2b", rowheight=25
        )
        style.map("Kutu.Treeview", background=[("selected", "#0078d7")])

        self.rule_tree = ttk.Treeview(
            table_frame,
            style="Kutu.Treeview",
            columns=("ref", "val", "status"),
            show="headings",
            height=15
        )
        self.rule_tree.heading("ref",    text="Kural")
        self.rule_tree.heading("val",    text="Aranan Değer")
        self.rule_tree.heading("status", text="St")

        self.rule_tree.column("ref",    width=90,  anchor="w")
        self.rule_tree.column("val",    width=160, anchor="w")
        self.rule_tree.column("status", width=30,  anchor="center", stretch=False)

        vsb = ttk.Scrollbar(table_frame, orient="vertical",   command=self.rule_tree.yview)
        hsb = ttk.Scrollbar(table_frame, orient="horizontal",  command=self.rule_tree.xview)
        self.rule_tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        self.rule_tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")

        self.rule_tree.tag_configure("found",     foreground="#00FF00")
        self.rule_tree.tag_configure("not_found", foreground="#FF6B6B")

        self.rule_tree.bind("<ButtonRelease-1>", self._on_table_click)

        # --- Design file section ---
        ctk.CTkLabel(
            self.sidebar, text="2. Tasarım Dosyası:",
            font=ctk.CTkFont(size=12, weight="bold"), anchor="w"
        ).grid(row=4, column=0, padx=20, pady=(10, 0), sticky="w")

        ctk.CTkButton(
            self.sidebar, text="🖼  Tasarım Yükle",
            command=self._select_design_file
        ).grid(row=5, column=0, padx=20, pady=6)

        self.design_path_label = ctk.CTkLabel(
            self.sidebar, text="Dosya seçilmedi",
            text_color="gray", wraplength=260, anchor="w"
        )
        self.design_path_label.grid(row=5, column=0, padx=20, pady=(48, 0), sticky="w")

        # Analyse button + status
        self.analyze_btn = ctk.CTkButton(
            self.sidebar, text="▶  Analizi Başlat",
            command=self._start_analysis,
            fg_color="#27AE60", hover_color="#1E8449"
        )
        self.analyze_btn.grid(row=7, column=0, padx=20, pady=(8, 4), sticky="s")

        self.status_label = ctk.CTkLabel(
            self.sidebar, text="Hazır", text_color="gray"
        )
        self.status_label.grid(row=8, column=0, padx=20, pady=(0, 16))

    # -----------------------------------------------------------------------
    # Main area (canvas)
    # -----------------------------------------------------------------------

    def _build_main_area(self):
        self.main_frame = ctk.CTkFrame(self, corner_radius=0)
        self.main_frame.grid(row=0, column=1, sticky="nsew", padx=10, pady=10)
        self.main_frame.grid_rowconfigure(0, weight=1)
        self.main_frame.grid_columnconfigure(0, weight=1)

        # Canvas
        self.canvas = Canvas(self.main_frame, bg="#333333", highlightthickness=0)
        self.canvas.grid(row=0, column=0, sticky="nsew")

        v_scroll = ttk.Scrollbar(self.main_frame, orient="vertical",   command=self.canvas.yview)
        h_scroll = ttk.Scrollbar(self.main_frame, orient="horizontal",  command=self.canvas.xview)
        v_scroll.grid(row=0, column=1, sticky="ns")
        h_scroll.grid(row=1, column=0, sticky="ew")
        self.canvas.configure(yscrollcommand=v_scroll.set, xscrollcommand=h_scroll.set)

        self.canvas.bind("<MouseWheel>",
                         lambda e: self.canvas.yview_scroll(int(-1 * (e.delta / 120)), "units"))
        self.canvas.bind("<Shift-MouseWheel>",
                         lambda e: self.canvas.xview_scroll(int(-1 * (e.delta / 120)), "units"))

        # Region selection mouse events
        self.canvas.bind("<ButtonPress-1>",   self._on_sel_start)
        self.canvas.bind("<B1-Motion>",       self._on_sel_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_sel_end)

        # Zoom bar
        zoom_bar = ctk.CTkFrame(self.main_frame, height=40)
        zoom_bar.grid(row=2, column=0, columnspan=2, sticky="ew", padx=10, pady=6)

        ctk.CTkLabel(zoom_bar, text="Ölçek:").pack(side="left", padx=(10, 4))
        self.zoom_var = ctk.StringVar(value="100%")
        zoom_opts = ["Sığdır", "25%", "50%", "75%", "100%", "150%", "200%"]
        ctk.CTkOptionMenu(
            zoom_bar, values=zoom_opts,
            variable=self.zoom_var,
            command=self._on_zoom_change,
            width=110
        ).pack(side="left", padx=4)

        # Rotation buttons
        ctk.CTkButton(
            zoom_bar, text="↺",
            width=36, height=28,
            font=ctk.CTkFont(size=18),
            fg_color="#555555", hover_color="#777777",
            command=lambda: self._rotate_image(-90)
        ).pack(side="left", padx=(12, 2))

        ctk.CTkButton(
            zoom_bar, text="↻",
            width=36, height=28,
            font=ctk.CTkFont(size=18),
            fg_color="#555555", hover_color="#777777",
            command=lambda: self._rotate_image(90)
        ).pack(side="left", padx=(2, 4))

        # Region select button
        self.sel_btn = ctk.CTkButton(
            zoom_bar, text="📐 Bölge Seç",
            width=110, height=28,
            fg_color="#005a9e", hover_color="#0078d7",
            command=self._toggle_selection
        )
        self.sel_btn.pack(side="left", padx=(14, 2))

        ctk.CTkButton(
            zoom_bar, text="✕ Bölgeyi Temizle",
            width=120, height=28,
            fg_color="#555555", hover_color="#777777",
            command=self._clear_selection
        ).pack(side="left", padx=(2, 4))

        self.region_label = ctk.CTkLabel(
            zoom_bar, text="", text_color="#66ccff",
            font=ctk.CTkFont(size=11)
        )
        self.region_label.pack(side="left", padx=6)

    # -----------------------------------------------------------------------
    # Actions
    # -----------------------------------------------------------------------

    def _select_rule_file(self):
        path = filedialog.askopenfilename(
            title="Kural Tablosu Seç",
            filetypes=[("Excel", "*.xlsx"), ("Tüm dosyalar", "*.*")]
        )
        if not path:
            return
        self._full_rule_path = path
        self.rule_path_label.configure(
            text=os.path.basename(path), text_color=("gray10", "gray90")
        )
        self._load_rule_table(path)

    def _select_design_file(self):
        path = filedialog.askopenfilename(
            title="Tasarım Dosyası Seç",
            filetypes=[
                ("Desteklenen dosyalar", "*.pdf *.png *.jpg *.jpeg *.bmp *.tiff *.webp"),
                ("PDF", "*.pdf"),
                ("Görseller", "*.png *.jpg *.jpeg *.bmp *.tiff *.webp"),
                ("Tüm dosyalar", "*.*"),
            ]
        )
        if not path:
            return
        ok, err = self.engine.load_file(path)
        if not ok:
            messagebox.showerror("Hata", f"Dosya yüklenemedi:\n{err}")
            return
        self._full_design_path = path
        self.design_path_label.configure(
            text=os.path.basename(path), text_color=("gray10", "gray90")
        )
        self._orig_image = self.engine.image.copy()
        self._rotation = 0
        self._base_image = self._orig_image.copy()
        self._highlight_rect = None
        self._render_canvas()
        self.status_label.configure(text="Tasarım yüklendi.", text_color="cyan")

    def _start_analysis(self):
        if not hasattr(self, "_full_rule_path"):
            self.status_label.configure(text="Önce kural tablosu seçin.", text_color="red")
            return
        if self._base_image is None:
            self.status_label.configure(text="Önce tasarım dosyası seçin.", text_color="red")
            return

        self.analyze_btn.configure(state="disabled")
        self.status_label.configure(text="Analiz yapılıyor…", text_color="orange")

        threading.Thread(target=self._run_analysis_thread, daemon=True).start()

    def _run_analysis_thread(self):
        try:
            region = self._sel_region  # None → tüm belge
            results = self.engine.run_analysis(self._full_rule_path, region=region)
            self.after(0, lambda: self._finish_analysis(results, None))
        except Exception as e:
            self.after(0, lambda: self._finish_analysis([], str(e)))

    def _finish_analysis(self, results, error):
        self.analyze_btn.configure(state="normal")
        if error:
            self.status_label.configure(text="Hata oluştu!", text_color="red")
            messagebox.showerror("Analiz Hatası", error)
            return

        self.row_index_to_result = {r["row_index"]: r for r in results}

        # Önce tüm satırları sıfırla (önceki analiz kalıntılarını temizle)
        for iid in self.rule_tree.get_children():
            self.rule_tree.set(iid, "status", "")
            self.rule_tree.item(iid, tags=())

        # Tüm bulunan eşleşmelerin rect listesini güncelle
        self._highlight_rects = []
        self._active_rect = None

        found_count = 0
        for r in results:
            item_id = self.excel_row_to_item_id.get(r["row_index"])
            if not item_id:
                continue
            if r["found"]:
                found_count += 1
                self.rule_tree.set(item_id, "status", "✔")
                self.rule_tree.set(item_id, "val", r["matched_term"][:60])
                self.rule_tree.item(item_id, tags=("found",))
                if r.get("rect"):
                    self._highlight_rects.append(r["rect"])
            # Bulunamayanlar: status boş, tag yok → varsayılan renk

        total = len(results)
        self.status_label.configure(
            text=f"Tamamlandı: {found_count}/{total} bulundu.",
            text_color="green"
        )
        # Tüm yeşil kutucukları göster
        self._render_canvas()

    def _on_table_click(self, event):
        item_id = self.rule_tree.identify_row(event.y)
        if not item_id:
            return
        row_index = self.item_id_to_excel_row.get(item_id)
        if row_index is None:
            return

        result = self.row_index_to_result.get(row_index)
        if result and result.get("found") and result.get("rect"):
            # Tıklanan satırı parlak yeşil olarak vurgula
            self._active_rect = result["rect"]
            self._render_canvas()

    def _on_zoom_change(self, choice):
        self._render_canvas()

    def _rotate_image(self, degrees: int):
        """Görseli verilen derece kadar döndür (saat yönü için +90)."""
        if self._orig_image is None:
            return
        self._rotation = (self._rotation + degrees) % 360
        # PIL rotate: pozitif = saat yönü tersine; expand=True boyutu korur
        self._base_image = self._orig_image.rotate(-self._rotation, expand=True)
        self._highlight_rects = []   # döndürünce eski highlight'lar geçersiz
        self._active_rect = None
        self._sel_region = None       # döndürünce seçim de geçersiz
        self._sel_rect_id = None
        self.region_label.configure(text="")
        self._render_canvas()

    # --- Region selection helpers -------------------------------------------

    def _toggle_selection(self):
        """Bölge seçme modunu aç/kapat."""
        self._sel_active = not self._sel_active
        if self._sel_active:
            self.canvas.config(cursor="cross")
            self.sel_btn.configure(fg_color="#c0392b", hover_color="#e74c3c",
                                   text="✕ Seçimi İptal Et")
        else:
            self.canvas.config(cursor="arrow")
            self.sel_btn.configure(fg_color="#005a9e", hover_color="#0078d7",
                                   text="📐 Bölge Seç")

    def _clear_selection(self):
        """Seçili bölgeyi temizle."""
        self._sel_region = None
        self._sel_start = None
        self._sel_rect_id = None
        self._sel_active = False
        self.canvas.config(cursor="arrow")
        self.sel_btn.configure(fg_color="#005a9e", hover_color="#0078d7",
                               text="📐 Bölge Seç")
        self.region_label.configure(text="")
        self._render_canvas()

    def _on_sel_start(self, event):
        if not self._sel_active or self._base_image is None:
            return
        # canvas scroll-adjusted coords
        cx = self.canvas.canvasx(event.x)
        cy = self.canvas.canvasy(event.y)
        self._sel_start = (cx, cy)
        if self._sel_rect_id:
            self.canvas.delete(self._sel_rect_id)
            self._sel_rect_id = None

    def _on_sel_drag(self, event):
        if not self._sel_active or self._sel_start is None:
            return
        cx = self.canvas.canvasx(event.x)
        cy = self.canvas.canvasy(event.y)
        x0, y0 = self._sel_start
        if self._sel_rect_id:
            self.canvas.coords(self._sel_rect_id, x0, y0, cx, cy)
        else:
            self._sel_rect_id = self.canvas.create_rectangle(
                x0, y0, cx, cy,
                outline="#00ff00", width=2, dash=(6, 3)
            )

    def _on_sel_end(self, event):
        if not self._sel_active or self._sel_start is None:
            return
        cx = self.canvas.canvasx(event.x)
        cy = self.canvas.canvasy(event.y)
        x0, y0 = self._sel_start
        # Normalize
        rx0, rx1 = (min(x0, cx), max(x0, cx))
        ry0, ry1 = (min(y0, cy), max(y0, cy))

        if abs(rx1 - rx0) < 10 or abs(ry1 - ry0) < 10:
            # Too small — ignore
            self._sel_start = None
            return

        # Convert canvas coords → image pixel coords
        z = self._zoom if self._zoom else 1.0
        img_x0 = int(rx0 / z)
        img_y0 = int(ry0 / z)
        img_x1 = int(rx1 / z)
        img_y1 = int(ry1 / z)

        if self._base_image:
            iw, ih = self._base_image.size
            img_x0 = max(0, min(iw, img_x0))
            img_y0 = max(0, min(ih, img_y0))
            img_x1 = max(0, min(iw, img_x1))
            img_y1 = max(0, min(ih, img_y1))

        self._sel_region = (img_x0, img_y0, img_x1, img_y1)
        self._sel_start = None
        w = img_x1 - img_x0
        h = img_y1 - img_y0
        self.region_label.configure(text=f"Seçili: {w}×{h}px")

        # Seçim modunu kapat
        self._sel_active = False
        self.canvas.config(cursor="arrow")
        self.sel_btn.configure(fg_color="#005a9e", hover_color="#0078d7",
                               text="📐 Bölge Seç")



    def _open_rule_detail(self):
        """Tüm kural satırlarını ayrı bir popup penceresinde göster."""
        rows = self.rule_tree.get_children()
        if not rows:
            from tkinter import messagebox as mb
            mb.showinfo("Bilgi", "Önce bir kural tablosu yükleyin.")
            return

        import tkinter as tk
        top = tk.Toplevel(self)
        top.title("Tüm Kurallar")
        top.configure(bg="#2b2b2b")
        top.geometry("640x480")
        top.grab_set()

        # Header
        tk.Label(
            top, text="🔭  Kural Tablosu — Tüm Satırlar",
            bg="#2b2b2b", fg="white",
            font=("Segoe UI", 13, "bold")
        ).pack(pady=(12, 6))

        frame = tk.Frame(top, bg="#2b2b2b")
        frame.pack(fill="both", expand=True, padx=12, pady=(0, 12))

        style = ttk.Style()
        style.configure(
            "Detail.Treeview",
            background="#2b2b2b", foreground="white",
            fieldbackground="#2b2b2b", rowheight=24
        )
        style.map("Detail.Treeview", background=[("selected", "#0078d7")])

        tree = ttk.Treeview(
            frame, style="Detail.Treeview",
            columns=("ref", "val", "status"),
            show="headings"
        )
        tree.heading("ref",    text="Kural")
        tree.heading("val",    text="Aranan Değer")
        tree.heading("status", text="Durum")
        tree.column("ref",    width=140, anchor="w")
        tree.column("val",    width=360, anchor="w")
        tree.column("status", width=80,  anchor="center")

        vsb = ttk.Scrollbar(frame, orient="vertical",  command=tree.yview)
        hsb = ttk.Scrollbar(frame, orient="horizontal", command=tree.xview)
        tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")
        frame.grid_rowconfigure(0, weight=1)
        frame.grid_columnconfigure(0, weight=1)

        tree.tag_configure("found",     foreground="#00FF00")
        tree.tag_configure("not_found", foreground="#FF6B6B")

        # Populate from main tree
        for iid in rows:
            vals = self.rule_tree.item(iid, "values")
            tags = self.rule_tree.item(iid, "tags")
            status_disp = "✔ Bulundu" if "found" in tags else ("✘ Bulunamadı" if "not_found" in tags else "—")
            tree.insert("", "end", values=(vals[0], vals[1], status_disp), tags=tags)

        tk.Button(
            top, text="Kapat",
            bg="#C0392B", fg="white",
            relief="flat", padx=16, pady=6,
            command=top.destroy
        ).pack(pady=(0, 12))

    # -----------------------------------------------------------------------
    # Canvas rendering
    # -----------------------------------------------------------------------

    def _compute_zoom(self) -> float:
        choice = self.zoom_var.get()
        if choice == "Sığdır":
            if self._base_image is None:
                return 1.0
            cw = self.canvas.winfo_width() or 800
            ch = self.canvas.winfo_height() or 600
            iw, ih = self._base_image.size
            return min(cw / iw, ch / ih) * 0.95
        return int(choice.replace("%", "")) / 100.0

    def _render_canvas(self):
        if self._base_image is None:
            return

        zoom = self._compute_zoom()
        self._zoom = zoom

        iw, ih = self._base_image.size
        nw, nh = max(1, int(iw * zoom)), max(1, int(ih * zoom))
        display = self._base_image.resize((nw, nh), Image.LANCZOS)

        # Draw green highlight overlays (all found matches + active/clicked one)
        has_any = self._highlight_rects or self._active_rect
        if has_any:
            overlay = Image.new("RGBA", display.size, (0, 0, 0, 0))
            draw = ImageDraw.Draw(overlay, "RGBA")
            pad = 4

            # All found matches — semi-transparent green fill
            for rect in self._highlight_rects:
                x0, y0, x1, y1 = rect
                sx0 = max(0, int(x0 * zoom) - pad)
                sy0 = max(0, int(y0 * zoom) - pad)
                sx1 = min(nw, int(x1 * zoom) + pad)
                sy1 = min(nh, int(y1 * zoom) + pad)
                draw.rectangle([sx0, sy0, sx1, sy1],
                               fill=(0, 200, 0, 80), outline="#00cc00", width=2)

            # Active / clicked match — brighter green, thicker border
            if self._active_rect:
                x0, y0, x1, y1 = self._active_rect
                sx0 = max(0, int(x0 * zoom) - pad - 2)
                sy0 = max(0, int(y0 * zoom) - pad - 2)
                sx1 = min(nw, int(x1 * zoom) + pad + 2)
                sy1 = min(nh, int(y1 * zoom) + pad + 2)
                draw.rectangle([sx0, sy0, sx1, sy1],
                               fill=(0, 255, 0, 130), outline="#00ff00", width=4)

            display = display.convert("RGBA")
            display = Image.alpha_composite(display, overlay)
            display = display.convert("RGB")

        self._display_image = ImageTk.PhotoImage(display)
        self.canvas.delete("all")
        self.canvas.create_image(0, 0, anchor="nw", image=self._display_image)
        self.canvas.configure(scrollregion=(0, 0, nw, nh))

        # Draw selection region on canvas (after image so it's on top)
        if self._sel_region:
            rx0, ry0, rx1, ry1 = self._sel_region
            sx0 = int(rx0 * zoom)
            sy0 = int(ry0 * zoom)
            sx1 = int(rx1 * zoom)
            sy1 = int(ry1 * zoom)
            self._sel_rect_id = self.canvas.create_rectangle(
                sx0, sy0, sx1, sy1,
                outline="#00ff00", width=2, dash=(6, 3)
            )

    # -----------------------------------------------------------------------
    # Rule table loading
    # -----------------------------------------------------------------------

    def _load_rule_table(self, path: str):
        for item in self.rule_tree.get_children():
            self.rule_tree.delete(item)
        self.excel_row_to_item_id.clear()
        self.item_id_to_excel_row.clear()
        self.row_index_to_result.clear()

        try:
            wb = openpyxl.load_workbook(path, data_only=True)
            sheet = wb.active
            for row in sheet.iter_rows(min_row=2):
                if all(c.value is None for c in row):
                    continue
                row_idx = row[0].row
                col_a = row[0].value or ""
                col_b = row[1].value if len(row) > 1 else None
                search_term = col_b if col_b is not None else col_a

                item_id = self.rule_tree.insert(
                    "", "end",
                    values=(str(col_a), str(search_term) if search_term else "", "")
                )
                self.excel_row_to_item_id[row_idx] = item_id
                self.item_id_to_excel_row[item_id] = row_idx

            self.status_label.configure(
                text=f"{len(self.excel_row_to_item_id)} kural yüklendi.",
                text_color="cyan"
            )
        except PermissionError:
            messagebox.showerror(
                "Hata",
                f"Dosya açık olabilir: {os.path.basename(path)}\nLütfen kapatıp tekrar deneyin."
            )
        except Exception as e:
            messagebox.showerror("Hata", f"Excel okunamadı:\n{e}")

    # -----------------------------------------------------------------------

    def _go_home(self):
        if self.on_back:
            self.on_back()
