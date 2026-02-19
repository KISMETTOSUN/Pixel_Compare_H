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

    def get_new_page_image(self, page_num, display_width=None, display_height=None, highlight_rect=None):
        """
        Returns a CTkImage of the specified page, scaled to fit display area.
        highlight_rect: optional [x0, y0, x1, y1] from PDF coordinates to draw a red box.
        """
        if not self.doc or page_num < 0 or page_num >= len(self.doc):
            return None
        
        page = self.doc.load_page(page_num)
        
        # Calculate zoom to fit
        zoom = 1.0
        if display_width and display_height:
            rect = page.rect
            width_ratio = display_width / rect.width
            height_ratio = display_height / rect.height
            zoom = min(width_ratio, height_ratio) * 0.9 # 90% to leave some margin
            
        mat = fitz.Matrix(zoom, zoom)
        pix = page.get_pixmap(matrix=mat)
        
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        
        # Draw highlight if provided
        if highlight_rect:
            from PIL import ImageDraw
            draw = ImageDraw.Draw(img, "RGBA")
            # Scale coordinates by zoom
            x0, y0, x1, y1 = highlight_rect
            scaled_rect = [x0 * zoom, y0 * zoom, x1 * zoom, y1 * zoom]
            
            # Draw semi-transparent red rectangle
            draw.rectangle(scaled_rect, fill=(255, 0, 0, 100), outline="red", width=2)
        
        return ctk.CTkImage(light_image=img, dark_image=img, size=(pix.width, pix.height))

    def get_total_pages(self):
        if self.doc:
            return len(self.doc)
        return 0
