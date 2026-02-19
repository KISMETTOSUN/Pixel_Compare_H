import customtkinter as ctk
from tkinter import ttk
from ui.home_frame import HomeFrame
from ui.main_window import ProspektusFrame
from ui.pixel_compare import PixelCompareFrame


class App(ctk.CTk):
    """Unified launcher: Home Screen -> Prospektüs Kontrolü / Pixel Kontrol"""
    
    def __init__(self):
        super().__init__()
        self.title("Üçgen - Doküman Kontrol Sistemi")
        self.geometry("1200x800")
        
        ctk.set_appearance_mode("dark")
        
        # Container
        self.container = ctk.CTkFrame(self, fg_color="transparent")
        self.container.pack(fill="both", expand=True)
        
        # Track current frame
        self.current_frame = None
        
        # Show home
        self.show_home()
    
    def show_home(self):
        self._clear_frame()
        self.geometry("900x600")
        self.title("Üçgen - Doküman Kontrol Sistemi")
        frame = HomeFrame(self.container, on_prospektus=self.show_prospektus, on_pixel=self.show_pixel)
        frame.pack(fill="both", expand=True)
        self.current_frame = frame
    
    def show_prospektus(self):
        self._clear_frame()
        self.geometry("1200x800")
        self.title("Üçgen - Prospektüs Kontrolü")
        frame = ProspektusFrame(self.container, on_back=self.show_home)
        frame.pack(fill="both", expand=True)
        self.current_frame = frame
    
    def show_pixel(self):
        self._clear_frame()
        self.geometry("1400x900")
        self.title("Üçgen - Pixel Kontrol")
        
        # Pixel Compare uses plain tkinter, need to set ttk style
        style = ttk.Style()
        style.theme_use('default')
        
        frame = PixelCompareFrame(self.container, on_back=self.show_home)
        frame.pack(fill="both", expand=True)
        self.current_frame = frame
    
    def _clear_frame(self):
        if self.current_frame:
            self.current_frame.destroy()
            self.current_frame = None


def main():
    app = App()
    app.mainloop()


if __name__ == "__main__":
    main()
