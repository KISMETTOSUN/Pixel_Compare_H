import customtkinter as ctk
from PIL import Image
import os


class HomeFrame(ctk.CTkFrame):
    """Ana sayfa - 2 modül seçimi: Prospektüs Kontrolü ve Pixel Kontrol"""
    
    def __init__(self, parent, on_prospektus=None, on_pixel=None):
        super().__init__(parent)
        self.configure(fg_color="#1a1a1a")
        
        self.on_prospektus = on_prospektus
        self.on_pixel = on_pixel
        
        # Center container
        self.grid_rowconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)
        self.grid_columnconfigure(0, weight=1)
        
        # Title with logo
        title_frame = ctk.CTkFrame(self, fg_color="transparent")
        title_frame.grid(row=0, column=0, sticky="s", pady=(0, 20))
        
        # Load logo image
        logo_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "üçgen_logo.png")
        if os.path.exists(logo_path):
            logo_image = ctk.CTkImage(
                light_image=Image.open(logo_path),
                dark_image=Image.open(logo_path),
                size=(200, 80)
            )
            ctk.CTkLabel(title_frame, image=logo_image, text="").pack()
        else:
            ctk.CTkLabel(
                title_frame, text="ÜÇGEN",
                font=ctk.CTkFont(size=42, weight="bold"),
                text_color="#FF8C00"
            ).pack()
        
        ctk.CTkLabel(
            title_frame, text="Doküman Kontrol Sistemi",
            font=ctk.CTkFont(size=16),
            text_color="#888888"
        ).pack(pady=(5, 0))
        
        # Cards container
        cards_frame = ctk.CTkFrame(self, fg_color="transparent")
        cards_frame.grid(row=1, column=0)
        
        # Card 1: Prospektüs Kontrolü
        self._create_card(
            cards_frame,
            title="📋  Prospektüs Kontrolü",
            command=self._on_prospektus_click,
            row=0
        )
        
        # Card 2: Pixel Kontrol
        self._create_card(
            cards_frame,
            title="🔍  Pixel Kontrol",
            command=self._on_pixel_click,
            row=1
        )
        
        # Footer
        ctk.CTkLabel(
            self, text="v1.0",
            font=ctk.CTkFont(size=11),
            text_color="#555555"
        ).grid(row=2, column=0, sticky="s", pady=(0, 15))
    
    def _create_card(self, parent, title, command, row):
        card = ctk.CTkButton(
            parent,
            text=title,
            font=ctk.CTkFont(size=18, weight="bold"),
            text_color="white",
            fg_color="#C0392B",
            hover_color="#E74C3C",
            corner_radius=15,
            width=280,
            height=109,
            command=command
        )
        card.grid(row=row, column=0, padx=20, pady=10)
    
    def _on_prospektus_click(self):
        if self.on_prospektus:
            self.on_prospektus()
    
    def _on_pixel_click(self):
        if self.on_pixel:
            self.on_pixel()
