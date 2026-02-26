import fitz  # PyMuPDF
from PIL import Image
import customtkinter as ctk

class PDFRenderer:
    def __init__(self):
        self.doc = None
        self.current_page_num = 0

    def load_pdf(self, file_path):
        """Loads a PDF file."""
        try:
            self.doc = fitz.open(file_path)
            self.current_page_num = 0
            return True
        except PermissionError:
            # We can't show messagebox here easily as it's a util. 
            # But the caller (main_window) checks return True/False. 
            # main_window calls this in select_control_file.
            # We should probably let exception propagate or print it so main_window can catch it?
            # Existing code prints error.
            print(f"Error loading PDF: Permission Denied for {file_path}")
            return False
        except Exception as e:
            print(f"Error loading PDF: {e}")
            return False

    def get_new_page_image(self, page_num, display_width=None, display_height=None, highlight_rect=None, highlight_rects=None, zoom_percent=None):
        """
        Returns a CTkImage of the specified page, scaled to fit display area.
        highlight_rect: optional [x0, y0, x1, y1] from PDF coordinates to draw a green box.
        highlight_rects: optional list of [x0, y0, x1, y1] to draw multiple green boxes.
        zoom_percent: optional int (e.g. 25, 50, 75, 100). If provided, uses fixed zoom instead of auto-fit.
        """
        if not self.doc or page_num < 0 or page_num >= len(self.doc):
            return None
        
        page = self.doc.load_page(page_num)
        
        # Calculate zoom
        if zoom_percent is not None:
            zoom = zoom_percent / 100.0
        elif display_width and display_height:
            rect = page.rect
            width_ratio = display_width / rect.width
            height_ratio = display_height / rect.height
            zoom = min(width_ratio, height_ratio) * 0.9 # 90% to leave some margin
        else:
            zoom = 1.0
            
        mat = fitz.Matrix(zoom, zoom)
        pix = page.get_pixmap(matrix=mat)
        
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        
        # Collect all rects to highlight
        all_rects = []
        if highlight_rect:
            all_rects.append(highlight_rect)
        if highlight_rects:
            all_rects.extend(highlight_rects)
        
        # Draw green highlights
        if all_rects:
            from PIL import ImageDraw
            draw = ImageDraw.Draw(img, "RGBA")
            for rect in all_rects:
                x0, y0, x1, y1 = rect
                scaled_rect = [x0 * zoom, y0 * zoom, x1 * zoom, y1 * zoom]
                # Draw semi-transparent green rectangle
                draw.rectangle(scaled_rect, fill=(0, 200, 0, 100), outline="#00cc00", width=3)
        
        return ctk.CTkImage(light_image=img, dark_image=img, size=(pix.width, pix.height))

    def get_total_pages(self):
        if self.doc:
            return len(self.doc)
        return 0
