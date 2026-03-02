import customtkinter as ctk
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from mpl_toolkits.mplot3d.art3d import Poly3DCollection
from matplotlib.patches import Polygon

class DenemeFrame(ctk.CTkFrame):
    def __init__(self, parent, on_back=None):
        super().__init__(parent)
        self.on_back = on_back

        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)

        # 1. SIDEBAR (Controls) - Matching the reference image style
        self.sidebar_frame = ctk.CTkFrame(self, width=350, corner_radius=10, fg_color="white")
        self.sidebar_frame.grid(row=0, column=0, sticky="nsew", padx=20, pady=20)
        self.sidebar_frame.grid_rowconfigure(10, weight=1)
        self.sidebar_frame.grid_propagate(False)

        # Title
        ctk.CTkLabel(self.sidebar_frame, text="Size", font=ctk.CTkFont(size=18, weight="bold"), text_color="black").grid(row=0, column=0, columnspan=3, padx=20, pady=(20, 10), sticky="w")

        # Labels Row
        ctk.CTkLabel(self.sidebar_frame, text="Length", font=ctk.CTkFont(size=12), text_color="gray").grid(row=1, column=0, padx=20, sticky="w")
        ctk.CTkLabel(self.sidebar_frame, text="Width", font=ctk.CTkFont(size=12), text_color="gray").grid(row=1, column=1, padx=5, sticky="w")
        ctk.CTkLabel(self.sidebar_frame, text="Height", font=ctk.CTkFont(size=12), text_color="gray").grid(row=1, column=2, padx=20, sticky="w")

        # Entries Row
        self.entry_l = ctk.CTkEntry(self.sidebar_frame, width=60, border_width=0, fg_color="transparent", text_color="black", font=ctk.CTkFont(size=14))
        self.entry_l.grid(row=2, column=0, padx=(20, 5), pady=5, sticky="w")
        self.entry_l.insert(0, "315")
        ctk.CTkLabel(self.sidebar_frame, text="mm", font=ctk.CTkFont(size=12), text_color="gray").grid(row=2, column=0, sticky="e")

        self.entry_w = ctk.CTkEntry(self.sidebar_frame, width=60, border_width=0, fg_color="transparent", text_color="black", font=ctk.CTkFont(size=14))
        self.entry_w.grid(row=2, column=1, padx=5, pady=5, sticky="w")
        self.entry_w.insert(0, "202")
        ctk.CTkLabel(self.sidebar_frame, text="mm", font=ctk.CTkFont(size=12), text_color="gray").grid(row=2, column=1, sticky="e")

        self.entry_h = ctk.CTkEntry(self.sidebar_frame, width=60, border_width=0, fg_color="transparent", text_color="black", font=ctk.CTkFont(size=14))
        self.entry_h.grid(row=2, column=2, padx=(5, 20), pady=5, sticky="w")
        self.entry_h.insert(0, "62")
        ctk.CTkLabel(self.sidebar_frame, text="mm", font=ctk.CTkFont(size=12), text_color="gray").grid(row=2, column=2, sticky="e")

        # Bind entries to update on return or focus out
        for entry in (self.entry_l, self.entry_w, self.entry_h):
            entry.bind("<Return>", lambda e: self.update_views())
            entry.bind("<FocusOut>", lambda e: self.update_views())

        # Thickness
        ctk.CTkLabel(self.sidebar_frame, text="Thickness", font=ctk.CTkFont(size=12), text_color="gray").grid(row=3, column=0, columnspan=3, padx=20, pady=(20, 5), sticky="w")
        
        thickness_frame = ctk.CTkFrame(self.sidebar_frame, fg_color="transparent")
        thickness_frame.grid(row=4, column=0, columnspan=3, padx=20, sticky="ew")
        thickness_frame.grid_columnconfigure(1, weight=1)
        
        ctk.CTkButton(thickness_frame, text="-", width=30, fg_color="transparent", text_color="black", hover_color="#f0f0f0").grid(row=0, column=0)
        self.thickness_var = ctk.StringVar(value="1.5")
        ctk.CTkLabel(thickness_frame, textvariable=self.thickness_var, text_color="black").grid(row=0, column=1)
        ctk.CTkButton(thickness_frame, text="+", width=30, fg_color="transparent", text_color="black", hover_color="#f0f0f0").grid(row=0, column=2)

        # Add Graphics Button
        self.add_graphics_btn = ctk.CTkButton(self.sidebar_frame, text="Add Graphics", fg_color="#f0f0f0", text_color="black", hover_color="#e0e0e0", border_width=1, border_color="#cccccc")
        self.add_graphics_btn.grid(row=5, column=0, columnspan=3, padx=20, pady=20, sticky="ew")

        # Style Options Title
        ctk.CTkLabel(self.sidebar_frame, text="Kapak Durumu", font=ctk.CTkFont(size=14, weight="bold"), text_color="black").grid(row=6, column=0, columnspan=3, padx=20, pady=(20, 10), sticky="w")
        
        # Lid Angle Slider
        self.angle_slider = ctk.CTkSlider(self.sidebar_frame, from_=0, to=180, command=self.on_slider_change, button_color="#C0392B", button_hover_color="#E74C3C")
        self.angle_slider.grid(row=7, column=0, columnspan=3, padx=20, pady=5, sticky="ew")
        self.angle_slider.set(0) # Closed by default to match screenshot

        # Update button (Keep just in case)
        self.update_btn = ctk.CTkButton(self.sidebar_frame, text="Güncelle", command=self.update_views, fg_color="#F39C12", hover_color="#D68910")
        self.update_btn.grid(row=8, column=0, columnspan=3, padx=20, pady=20, sticky="ew")

        # Back button at the bottom
        self.back_btn = ctk.CTkButton(self.sidebar_frame, text="← Ana Sayfaya Dön", command=self._go_home, fg_color="#C0392B", hover_color="#E74C3C")
        self.back_btn.grid(row=11, column=0, columnspan=3, padx=20, pady=20, sticky="ew")

        # 2. MAIN AREA (Visualizations)
        self.main_frame = ctk.CTkFrame(self, fg_color="#f8f9fa", corner_radius=10) # Light background like screenshot
        self.main_frame.grid(row=0, column=1, sticky="nsew", padx=(0, 20), pady=20)
        
        # Split main area: Top for 2D, Bottom for 3D
        self.main_frame.grid_rowconfigure(0, weight=1) # 2D View
        self.main_frame.grid_rowconfigure(1, weight=1) # 3D View
        self.main_frame.grid_columnconfigure(0, weight=1)

        # -----------------------------------------------------
        # 2D Canvas (Top)
        # -----------------------------------------------------
        self.fig_2d = plt.figure(figsize=(8, 4), facecolor="#f8f9fa")
        # Remove all borders/margins from the figure itself
        self.fig_2d.subplots_adjust(left=0, right=1, bottom=0, top=1)
        self.ax_2d = self.fig_2d.add_subplot(111)
        self.ax_2d.set_facecolor("#f8f9fa")
        self.ax_2d.set_axis_off()

        self.canvas_2d = FigureCanvasTkAgg(self.fig_2d, master=self.main_frame)
        self.canvas_widget_2d = self.canvas_2d.get_tk_widget()
        self.canvas_widget_2d.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)

        # -----------------------------------------------------
        # 2D Canvas Interactive Events
        # -----------------------------------------------------
        self.canvas_2d.mpl_connect('scroll_event', self.zoom_2d)
        self.canvas_2d.mpl_connect('button_press_event', self.on_press_2d)
        self.canvas_2d.mpl_connect('button_release_event', self.on_release_2d)
        self.canvas_2d.mpl_connect('motion_notify_event', self.on_motion_2d)
        self._pan_start = None

        # -----------------------------------------------------
        # 3D Canvas (Bottom)
        # -----------------------------------------------------
        self.fig_3d = plt.figure(figsize=(8, 5), facecolor="#f8f9fa")
        self.ax_3d = self.fig_3d.add_subplot(111, projection='3d')
        self.ax_3d.set_facecolor("#f8f9fa")
        self.ax_3d.set_axis_off()

        self.canvas_3d = FigureCanvasTkAgg(self.fig_3d, master=self.main_frame)
        self.canvas_widget_3d = self.canvas_3d.get_tk_widget()
        self.canvas_widget_3d.grid(row=1, column=0, sticky="nsew", padx=10, pady=10)

        # Initial Draw
        self.update_views()

    def on_slider_change(self, value):
        self.update_3d_view()

    # --- 2D Interactive Methods ---
    def zoom_2d(self, event):
        if event.inaxes != self.ax_2d: return
        
        base_scale = 1.2
        if event.button == 'up': scale_factor = 1 / base_scale # zoom in
        elif event.button == 'down': scale_factor = base_scale # zoom out
        else: return
        
        xdata = event.xdata
        ydata = event.ydata
        if xdata is None or ydata is None: return

        cur_xlim = self.ax_2d.get_xlim()
        cur_ylim = self.ax_2d.get_ylim()
        
        x_left = xdata - cur_xlim[0]
        x_right = cur_xlim[1] - xdata
        y_bottom = ydata - cur_ylim[0]
        y_top = cur_ylim[1] - ydata
        
        self.ax_2d.set_xlim([xdata - x_left * scale_factor, xdata + x_right * scale_factor])
        self.ax_2d.set_ylim([ydata - y_bottom * scale_factor, ydata + y_top * scale_factor])
        
        # Disable auto-scaling when user manually zooms
        self.ax_2d.set_autoscale_on(False)
        self.canvas_2d.draw_idle()

    def on_press_2d(self, event):
        if event.button == 1 and event.inaxes == self.ax_2d: # Left click
            self._pan_start = (event.xdata, event.ydata)

    def on_release_2d(self, event):
        self._pan_start = None

    def on_motion_2d(self, event):
        if self._pan_start is None or event.inaxes != self.ax_2d: return
        
        dx = event.xdata - self._pan_start[0]
        dy = event.ydata - self._pan_start[1]
        
        if dx == 0 and dy == 0: return

        cur_xlim = self.ax_2d.get_xlim()
        cur_ylim = self.ax_2d.get_ylim()
        
        self.ax_2d.set_xlim([cur_xlim[0] - dx, cur_xlim[1] - dx])
        self.ax_2d.set_ylim([cur_ylim[0] - dy, cur_ylim[1] - dy])
        
        # Disable auto-scaling when user manually pans
        self.ax_2d.set_autoscale_on(False)
        self.canvas_2d.draw_idle()
        
    # -----------------------------

    def update_views(self):
        self.update_2d_view()
        self.update_3d_view()

    def update_2d_view(self):
        try:
            L = float(self.entry_l.get())
            W = float(self.entry_w.get())
            H = float(self.entry_h.get())
        except ValueError:
            return
            
        self.ax_2d.clear()
        self.ax_2d.set_axis_off()
        
        # Colors for 2D diagram
        fill_color = 'white'
        edge_color = 'green'
        fold_color = 'red' # dashed
        
        # We will draw a flattened mailer box (die-cut template)
        # Use matplotlib shapes without altering limits prematurely
        x0, y0 = 0, 0
        
        # Helper to draw polygons
        def draw_poly(points, edgecolor=edge_color, facecolor=fill_color, linestyle='-'):
            poly = Polygon(points, closed=True, edgecolor=edgecolor, facecolor=facecolor, linestyle=linestyle, linewidth=1.5)
            self.ax_2d.add_patch(poly)
            
        def draw_line(p1, p2, color=fold_color, style='--'):
            self.ax_2d.plot([p1[0], p2[0]], [p1[1], p2[1]], color=color, linestyle=style, linewidth=1)

        # Before drawing the box, let's draw a large invisible "canvas" area to force the aspect ratio to include the margins
        flap_h = H * 0.8
        min_x = x0 - H - W*0.4 - 20 # Add 20mm left margin
        max_x = x0 + W + H + W*0.4 + 20 # Add 20mm right margin
        min_y = y0 - H - flap_h - 20 # Add 20mm bottom margin
        max_y = y0 + L + H + L + flap_h + 20 # Add 20mm top margin
        
        # Draw a white background rectangle that covers this entire padded area so it's always included in the view
        bg_rect = [[min_x, min_y], [max_x, min_y], [max_x, max_y], [min_x, max_y]]
        draw_poly(bg_rect, edgecolor='none', facecolor='#ffffff')

        # Base 
        b_bl = [x0, y0]
        b_br = [x0+W, y0]
        b_tr = [x0+W, y0+L]
        b_tl = [x0, y0+L]
        
        # Draw Base Outline (solid)
        draw_poly([b_bl, b_br, b_tr, b_tl])
        
        # Front Wall (bottom of base)
        f_bl = [x0, y0-H]
        f_br = [x0+W, y0-H]
        draw_poly([f_bl, f_br, b_br, b_bl])
        draw_line(b_bl, b_br) # Fold line
        
        # Front Tuck Flap
        flap_h = H * 0.8
        ft_bl = [x0+W*0.05, y0-H-flap_h]
        ft_br = [x0+W*0.95, y0-H-flap_h]
        draw_poly([ft_bl, ft_br, f_br, f_bl])
        draw_line(f_bl, f_br)
        
        # Back Wall (top of base)
        bk_tl = [x0, y0+L+H]
        bk_tr = [x0+W, y0+L+H]
        draw_poly([b_tl, b_tr, bk_tr, bk_tl])
        draw_line(b_tl, b_tr)
        
        # Main Lid (attached to back wall)
        l_tl = [x0, y0+L+H+L]
        l_tr = [x0+W, y0+L+H+L]
        draw_poly([bk_tl, bk_tr, l_tr, l_tl])
        draw_line(bk_tl, bk_tr)
        
        # Lid Flap
        lf_tl = [x0+W*0.05, y0+L+H+L+flap_h]
        lf_tr = [x0+W*0.95, y0+L+H+L+flap_h]
        draw_poly([l_tl, l_tr, lf_tr, lf_tl])
        draw_line(l_tl, l_tr)

        # Left Wall (attached to base)
        lw_tl = [x0-H, y0+L]
        lw_bl = [x0-H, y0]
        draw_poly([lw_bl, b_bl, b_tl, lw_tl])
        draw_line(lw_bl, b_bl)
        draw_line(lw_tl, b_tl)
        
        # Right Wall (attached to base)
        rw_tr = [x0+W+H, y0+L]
        rw_br = [x0+W+H, y0]
        draw_poly([b_br, rw_br, rw_tr, b_tr])
        draw_line(b_br, rw_br)
        draw_line(b_tr, rw_tr)

        # Left/Right Dust Flaps (attached to side walls)
        ldf_tl = [x0-H-W*0.4, y0+L]
        ldf_bl = [x0-H-W*0.4, y0]
        draw_poly([ldf_bl, lw_bl, lw_tl, ldf_tl], linestyle='-')
        draw_line(lw_bl, lw_tl)
        
        rdf_tr = [x0+W+H+W*0.4, y0+L]
        rdf_br = [x0+W+H+W*0.4, y0]
        draw_poly([rw_br, rdf_br, rdf_tr, rw_tr], linestyle='-')
        draw_line(rw_br, rw_tr)
        
        # Force aspect ratio visually but allow dragging/zooming without data limit snapping
        self.ax_2d.set_aspect('equal', adjustable='box')

        # Provide base limits based on actual box dimensions plus the background padding
        self.ax_2d.set_xlim(min_x, max_x)
        self.ax_2d.set_ylim(min_y, max_y)

        self.canvas_2d.draw()

    def update_3d_view(self):
        try:
            L = float(self.entry_l.get())
            W = float(self.entry_w.get())
            H = float(self.entry_h.get())
        except ValueError:
            return  # Wait for valid input
            
        lid_angle_deg = float(self.angle_slider.get())
        lid_angle_rad = np.radians(lid_angle_deg)

        self.ax_3d.clear()
        self.ax_3d.set_axis_off() # Keep axes hidden

        # Box colors matching screenshot (Cardboard Kraft)
        base_color = '#C5A880'
        top_color = '#D1B48C'
        side_color = '#B3966D'
        edge_color = '#A08055'
        alpha_val = 1.0

        # Define 8 corners of the closed main box
        # Base: z=0
        p0 = [0, 0, 0]
        p1 = [L, 0, 0]
        p2 = [L, W, 0]
        p3 = [0, W, 0]
        # Top: z=H
        p4 = [0, 0, H]
        p5 = [L, 0, H]
        p6 = [L, W, H]
        p7 = [0, W, H]

        faces = []
        facecolors = []

        # Bottom
        faces.append([p0, p1, p2, p3])
        facecolors.append(base_color)
        
        # Front (y=0)
        faces.append([p0, p1, p5, p4])
        facecolors.append(side_color)
        
        # Back (y=W)
        faces.append([p3, p2, p6, p7])
        facecolors.append(side_color)
        
        # Left (x=0)
        faces.append([p0, p3, p7, p4])
        facecolors.append(side_color)
        
        # Right (x=L)
        faces.append([p1, p2, p6, p5])
        facecolors.append(side_color)

        # Flaps and details to make it look like the Mailer Box in screenshot
        # The screenshot shows a closed mailer box with folded front flaps.
        # We'll simulate this by adding small flap details on the top face when closed, 
        # or rotating the main lid when opened.
        
        dy_new = -W * np.cos(lid_angle_rad)
        dz_new = W * np.sin(lid_angle_rad)
        
        p_lid_left = [0, W + dy_new, H + dz_new]
        p_lid_right = [L, W + dy_new, H + dz_new]

        # The main lid face
        lid_face = [p7, p6, p_lid_right, p_lid_left]
        faces.append(lid_face)
        facecolors.append(top_color)

        # Front tuck flap of the lid (goes down into the box when closed)
        # When lid_angle is 0 (closed), it points down (-Z).
        # We'll rotate it relative to the lid's edge
        flap_len = H * 0.8
        
        # Flap rotation relative to lid: always 90 degrees inward.
        # So flap angle in world space = lid_angle + 90
        flap_angle_rad = lid_angle_rad + np.pi/2
        
        f_dy = -flap_len * np.cos(flap_angle_rad)
        f_dz = flap_len * np.sin(flap_angle_rad)
        
        p_flap_left = [p_lid_left[0], p_lid_left[1] + f_dy, p_lid_left[2] + f_dz]
        p_flap_right = [p_lid_right[0], p_lid_right[1] + f_dy, p_lid_right[2] + f_dz]
        
        flap_face = [p_lid_left, p_lid_right, p_flap_right, p_flap_left]
        faces.append(flap_face)
        facecolors.append(side_color)

        # Also add small side dust flaps if lid is open to make it look realistic
        if lid_angle_deg > 10:
            dust_w = W * 0.4
            
            # Left dust flap (attached to x=0, z=H, from y=0 to y=W)
            dl1 = [0, 0, H]
            dl2 = [0, W, H]
            # Rotated slightly inwards
            dl3 = [dust_w * np.sin(np.pi/6), W, H + dust_w * np.cos(np.pi/6)]
            dl4 = [dust_w * np.sin(np.pi/6), 0, H + dust_w * np.cos(np.pi/6)]
            faces.append([dl1, dl2, dl3, dl4])
            facecolors.append(base_color)
            
            # Right dust flap
            dr1 = [L, 0, H]
            dr2 = [L, W, H]
            dr3 = [L - dust_w * np.sin(np.pi/6), W, H + dust_w * np.cos(np.pi/6)]
            dr4 = [L - dust_w * np.sin(np.pi/6), 0, H + dust_w * np.cos(np.pi/6)]
            faces.append([dr1, dr2, dr3, dr4])
            facecolors.append(base_color)
            
            # Draw inside bottom to show depth
            inner_bottom = [[0, 0, 0.1], [L, 0, 0.1], [L, W, 0.1], [0, W, 0.1]]
            faces.append(inner_bottom)
            facecolors.append('#B08A60')

        # Plot the faces
        collection = Poly3DCollection(faces, facecolors=facecolors, linewidths=0.5, edgecolors=edge_color, alpha=alpha_val)
        self.ax_3d.add_collection3d(collection)
        
        # Add the little cutouts/tabs on the front facing lid edge (visible when closed)
        if lid_angle_deg < 5:
            # Draw two small dark gray rectangles to simulate the tabs from the screenshot
            tab_w = L * 0.05
            tab_d = W * 0.02
            
            tab1_x = L * 0.15
            tab2_x = L * 0.85 - tab_w
            
            tab1 = [[tab1_x, -0.1, H], [tab1_x+tab_w, -0.1, H], [tab1_x+tab_w, tab_d, H], [tab1_x, tab_d, H]]
            tab2 = [[tab2_x, -0.1, H], [tab2_x+tab_w, -0.1, H], [tab2_x+tab_w, tab_d, H], [tab2_x, tab_d, H]]
            
            tabs_col = Poly3DCollection([tab1, tab2], facecolors='#808080', edgecolors='none', alpha=1.0)
        self.ax_3d.add_collection3d(tabs_col)

        # Set equal aspect ratio to avoid distortion
        max_range = np.array([L, W, H]).max() / 2.0
        
        mid_x = L / 2.0
        mid_y = W / 2.0
        mid_z = H / 2.0

        self.ax_3d.set_xlim(mid_x - max_range, mid_x + max_range)
        self.ax_3d.set_ylim(mid_y - max_range, mid_y + max_range)
        self.ax_3d.set_zlim(mid_z - max_range, mid_z + max_range + (W if lid_angle_deg > 10 else 0))

        # View angle matching screenshot (isometric-like)
        self.ax_3d.view_init(elev=25, azim=-55)

        self.canvas_3d.draw()

    def _go_home(self):
        if self.on_back:
            self.on_back()
