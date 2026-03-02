import customtkinter as ctk
from PIL import Image
import os


class HomeFrame(ctk.CTkFrame):
    """Ana sayfa - 3 modül seçimi: Prospektüs Kontrolü, Tasarım Karşılaştır, Kutu Tasarım Kontrolü"""
    
    def __init__(self, parent, on_prospektus=None, on_pixel=None, on_kutu=None, on_deneme=None):
        super().__init__(parent)
        self.configure(fg_color="#1a1a1a")
        
        self.on_prospektus = on_prospektus
        self.on_pixel = on_pixel
        self.on_kutu = on_kutu
        self.on_deneme = on_deneme
        
        # Center container
        self.grid_rowconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)
        self.grid_columnconfigure(0, weight=1)
        
        # Title with logo
        title_frame = ctk.CTkFrame(self, fg_color="transparent")
        title_frame.grid(row=0, column=0, sticky="s", pady=(0, 20))
        
        # Load logo image
        logo_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "1-Prospektus", "üçgen_logo.png")
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
            icon="📋",
            title="Prospektüs Kontrolü",
            command=self._on_prospektus_click,
            row=0
        )
        
        # Card 2: Tasarım Karşılaştır
        self._create_card(
            cards_frame,
            icon="🔍",
            title="Tasarım Karşılaştır",
            command=self._on_pixel_click,
            row=1
        )
        
        # Card 3: Kutu Tasarım Kontrolü
        self._create_card(
            cards_frame,
            icon="📦",
            title="Kutu Tasarım Kontrolü",
            command=self._on_kutu_click,
            row=2
        )
        
        # Card 4: Deneme
        self._create_card(
            cards_frame,
            icon="🧪",
            title="Deneme",
            command=self._on_deneme_click,
            row=3
        )
        
        # Footer
        self.version_label = ctk.CTkLabel(
            self, text="v1.5",
            font=ctk.CTkFont(size=11),
            text_color="#555555"
        ).grid(row=2, column=0, sticky="s", pady=(0, 15))
    
    def _create_card(self, parent, icon, title, command, row):
        """Simge ayrı büyük label, yazı aynı hizada sabit konumda."""
        CARD_W, CARD_H = 300, 109
        ICON_FONT_SIZE = 34   # 27px × 1.25 ≈ 34px
        TEXT_FONT_SIZE = 18
        ICON_W = 80           # simge alanı genişliği

        # Dış çerçeve – buton gibi davranır
        frame = ctk.CTkFrame(
            parent,
            fg_color="#C0392B",
            corner_radius=15,
            width=CARD_W,
            height=CARD_H
        )
        frame.grid(row=row, column=0, padx=20, pady=10)
        frame.grid_propagate(False)
        frame.grid_columnconfigure(0, minsize=ICON_W)
        frame.grid_columnconfigure(1, weight=1)
        frame.grid_rowconfigure(0, weight=1)

        # Simge
        icon_lbl = ctk.CTkLabel(
            frame,
            text=icon,
            font=ctk.CTkFont(size=ICON_FONT_SIZE),
            text_color="white",
            fg_color="transparent",
            width=ICON_W,
            anchor="center"
        )
        icon_lbl.grid(row=0, column=0, sticky="nsew")

        # Yazı – soldan hizalı, dikey ortalı
        text_lbl = ctk.CTkLabel(
            frame,
            text=title,
            font=ctk.CTkFont(size=TEXT_FONT_SIZE, weight="bold"),
            text_color="white",
            fg_color="transparent",
            anchor="w"
        )
        text_lbl.grid(row=0, column=1, sticky="w", padx=(0, 10))

        # Tıklama olaylarını tüm widget'lara bağla
        for widget in (frame, icon_lbl, text_lbl):
            widget.bind("<Button-1>", lambda e, cmd=command: cmd())
            widget.bind("<Enter>", lambda e, f=frame: f.configure(fg_color="#E74C3C"))
            widget.bind("<Leave>", lambda e, f=frame: f.configure(fg_color="#C0392B"))
    
    def _on_prospektus_click(self):
        if self.on_prospektus:
            self.on_prospektus()
    
    def _on_pixel_click(self):
        if self.on_pixel:
            self.on_pixel()
    
    def _on_kutu_click(self):
        if self.on_kutu:
            self.on_kutu()
            
    def _on_deneme_click(self):
        if self.on_deneme:
            self.on_deneme()
