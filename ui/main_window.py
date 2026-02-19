from utils.pdf_renderer import PDFRenderer
from utils.analysis_engine import AnalysisEngine
from PIL import Image
import customtkinter as ctk
from tkinter import filedialog, messagebox, ttk
import threading
import os
import os
import openpyxl

class MainWindow(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Document Control App")
        self.geometry("1100x700")
        
        self.pdf_renderer = PDFRenderer()
        self.analysis_engine = AnalysisEngine()
        self.current_page = 0
        self.total_pages = 0
        self.analysis_results_map = {} # Map row_index to result dict
        self.row_data_map = {} # Map row_index to full row data tuple from Excel

        # Configure grid layout (1x2)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # Sidebar setup (same as before)
        self.setup_sidebar()

        # Main Content Area (PDF Viewer)
        self.main_frame = ctk.CTkFrame(self, corner_radius=0)
        self.main_frame.grid(row=0, column=1, sticky="nsew", padx=20, pady=20)
        self.main_frame.grid_rowconfigure(0, weight=1)
        self.main_frame.grid_columnconfigure(0, weight=1)
        
        # Scrollable frame for PDF content if needed, or just a Label
        self.pdf_display_label = ctk.CTkLabel(self.main_frame, text="")
        self.pdf_display_label.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        
        # Navigation Frame
        self.nav_frame = ctk.CTkFrame(self.main_frame, height=40)
        self.nav_frame.grid(row=1, column=0, sticky="ew", padx=10, pady=10)
        
        self.prev_btn = ctk.CTkButton(self.nav_frame, text="Previous", command=self.prev_page, state="disabled")
        self.prev_btn.pack(side="left", padx=10, pady=5)
        
        self.page_label = ctk.CTkLabel(self.nav_frame, text="Page 0 of 0")
        self.page_label.pack(side="left", padx=10, pady=5)
        
        self.next_btn = ctk.CTkButton(self.nav_frame, text="Next", command=self.next_page, state="disabled")
        self.next_btn.pack(side="left", padx=10, pady=5)

    def setup_sidebar(self):
        # Create sidebar frame with widgets
        self.sidebar_frame = ctk.CTkFrame(self, width=300, corner_radius=0) # Increased width for table
        self.sidebar_frame.grid(row=0, column=0, sticky="nsew")
        self.sidebar_frame.grid_rowconfigure(8, weight=1) # Push content up

        self.logo_label = ctk.CTkLabel(self.sidebar_frame, text="DocControl", font=ctk.CTkFont(size=20, weight="bold"))
        self.logo_label.grid(row=0, column=0, padx=20, pady=(20, 10))

        # Load Latest Button
        self.load_latest_btn = ctk.CTkButton(self.sidebar_frame, text="En Güncel Datayı Çek", command=self.load_latest_data, fg_color="#F39C12", hover_color="#D68910")
        self.load_latest_btn.grid(row=0, column=0, padx=20, pady=(20, 10), sticky="e") # Put it next to Logo or replace logo? 
        # Better: Put it under logo.
        self.load_latest_btn.grid(row=1, column=0, padx=20, pady=(0, 20))

        # Rule Document Selection
        self.rule_label = ctk.CTkLabel(self.sidebar_frame, text="Rule Document:", anchor="w")
        self.rule_label.grid(row=2, column=0, padx=20, pady=(0, 0))
        
        self.select_rule_btn = ctk.CTkButton(self.sidebar_frame, text="Select File", command=self.select_rule_file)
        self.select_rule_btn.grid(row=3, column=0, padx=20, pady=10)
        
        self.selected_rule_path_label = ctk.CTkLabel(self.sidebar_frame, text="No file selected", text_color="gray", wraplength=250)
        self.selected_rule_path_label.grid(row=4, column=0, padx=20, pady=(0, 10))

        # Rule Table Frame (for Scrollbars)
        self.table_frame = ctk.CTkFrame(self.sidebar_frame)
        self.table_frame.grid(row=5, column=0, padx=10, pady=(0, 10), sticky="nsew") # Moved to row 5
        self.sidebar_frame.grid_rowconfigure(5, weight=1) # Let table expand
        self.table_frame.grid_columnconfigure(0, weight=1)
        self.table_frame.grid_rowconfigure(0, weight=1)

        self.style = ttk.Style()
        self.style.theme_use("default")
        self.style.configure("Treeview", 
                             background="#2b2b2b", 
                             foreground="white", 
                             fieldbackground="#2b2b2b",
                             rowheight=25)
        self.style.map('Treeview', background=[('selected', '#0078d7')])
        
        # Define columns: View, Reference (A), Value (B), Status
        self.rule_tree = ttk.Treeview(self.table_frame, columns=("view", "ref", "val", "status"), show="headings", height=15)
        self.rule_tree.heading("view", text="") # Icon column header empty
        self.rule_tree.heading("ref", text="Ref")
        self.rule_tree.heading("val", text="Data")
        self.rule_tree.heading("status", text="St")
        
        self.rule_tree.column("view", width=30, anchor="center", stretch=False)
        self.rule_tree.column("ref", width=80)
        self.rule_tree.column("val", width=120)
        self.rule_tree.column("status", width=30, anchor="center")
        
        # Scrollbars
        self.vsb = ttk.Scrollbar(self.table_frame, orient="vertical", command=self.rule_tree.yview)
        self.hsb = ttk.Scrollbar(self.table_frame, orient="horizontal", command=self.rule_tree.xview)
        self.rule_tree.configure(yscrollcommand=self.vsb.set, xscrollcommand=self.hsb.set)
        
        self.rule_tree.grid(row=0, column=0, sticky="nsew")
        self.vsb.grid(row=0, column=1, sticky="ns")
        self.hsb.grid(row=1, column=0, sticky="ew")
        
        # Bind click event
        self.rule_tree.bind("<ButtonRelease-1>", self.on_table_click)
        
        # Tag configuration for colors
        # self.rule_tree.tag_configure('found', background='green', foreground='white') # Deprecated by user request for tick only?
        # User said: "d kolonunda yeşil tik işareti olsun". 
        # But also "bulunan satıra tıklayınca". 
        # I'll keep default background but add tick in Status column.
        # Check if user wants background logic kept. "b kolonundaki data yeşil olsun" was previous req.
        # Latest req: "d kolonunda yeşil tik işareti olsun". 
        # I'll stick to just tick for now, effectively implementing the latest request.

        # Control Document Selection
        self.control_label = ctk.CTkLabel(self.sidebar_frame, text="Control PDF:", anchor="w")
        self.control_label.grid(row=5, column=0, padx=20, pady=(10, 0))

        self.select_control_btn = ctk.CTkButton(self.sidebar_frame, text="Select PDF", command=self.select_control_file)
        self.select_control_btn.grid(row=6, column=0, padx=20, pady=10)

        self.selected_control_path_label = ctk.CTkLabel(self.sidebar_frame, text="No file selected", text_color="gray", wraplength=250)
        self.selected_control_path_label.grid(row=7, column=0, padx=20, pady=(0, 20))

        # Analysis Button
        self.analyze_btn = ctk.CTkButton(self.sidebar_frame, text="Run Analysis", command=self.start_analysis, fg_color="green", hover_color="darkgreen")
        self.analyze_btn.grid(row=9, column=0, padx=20, pady=20, sticky="s")
        
        self.status_label = ctk.CTkLabel(self.sidebar_frame, text="Ready", text_color="gray")
        self.status_label.grid(row=10, column=0, padx=20, pady=(0, 20))

    def start_analysis(self):
        rule_path = self.selected_rule_path_label.cget("text")
        control_path = self.selected_control_path_label.cget("text")
        
        if "No file selected" in rule_path or "No file selected" in control_path:
            self.status_label.configure(text="Please select both files.", text_color="red")
            return

        if not hasattr(self, 'full_rule_path') or not hasattr(self, 'full_control_path'):
             self.status_label.configure(text="Internal Error: Paths lost.", text_color="red")
             return

        # Pre-check for file locks (PermissionError)
        # Excel locks file for writing. Opening with 'rb' (read binary) often succeeds if Excel allows shared read.
        # To strictly check if we can "Use" it or if it's "Open" in a way that might block us later (or if user wants strict check),
        # we should try to open for modification or exclusive access?
        # Actually, if we just want to warn "It is open", checking write access is a good proxy because Excel takes write lock.
        # Let's try opening with 'r+' (read/write) which requires write permission.
        
        try:
            # Check Excel
            with open(self.full_rule_path, 'r+'): 
                pass
        except PermissionError:
             messagebox.showerror("Error", f"Excel dosyası açık: {os.path.basename(self.full_rule_path)}\nAnalize başlamadan önce lütfen kapatın.")
             return
        except Exception as e:
             # 'r+' might fail if readonly file? But user wants "Open" check.
             # If it fails for other reasons, maybe it's fine? 
             # But if we can't write, maybe we can't save results later (if we implemented that)?
             # The user just said "analyzing diyor", implying it didn't fail fast enough.
             # Re-reading: "dosya açık ama analiz ediliyor diyor". 
             # So the previous 'rb' check passed.
             # 'r+' should trigger error if Excel is open.
             # If file is read-only attribute, this might falsely trigger.
             # But standard Excel open locks it.
             pass 

        try:
            # Check PDF (Acrobat might not lock as strictly as Excel, but often does if editing)
            # If just reading, Adobe Reader might allow shared read.
            # But the requirement is "Make sure it is closed". 
            with open(self.full_control_path, 'r+'): 
                pass
        except PermissionError:
             messagebox.showerror("Error", f"PDF dosyası açık: {os.path.basename(self.full_control_path)}\nAnalize başlamadan önce lütfen kapatın.")
             return
        except Exception:
             pass

        self.status_label.configure(text="Analyzing...", text_color="orange")
        self.analyze_btn.configure(state="disabled")

        # Run in thread to keep UI responsive
        threading.Thread(target=self.run_backend_analysis, daemon=True).start()

    def run_backend_analysis(self):
        try:
            result = self.analysis_engine.run_analysis(self.full_rule_path, self.full_control_path)
        except Exception as e:
            result = {"status": f"Critical Error in Analysis Thread: {e}", "results": []}
        
        # Update UI in main thread (thread-safe way usually safer, but tkinter often tolerates simple updates or use after)
        self.after(0, lambda: self.finish_analysis(result))

    def finish_analysis(self, result):
        self.analyze_btn.configure(state="normal")
        status_msg = result.get("status", "")
        # The result includes "results" list. 
        # Each item: {row_index, found, locations: [{page, rect}]}
        results_list = result.get("results", [])

        if "Complete" in status_msg or "Success" in status_msg:
             self.status_label.configure(text="Analysis Complete!", text_color="green")
             self.analysis_results_map = {} # Reset and populate map
             
             for res in results_list:
                 row_idx = res["row_index"]
                 found = res["found"]
                 
                 # Store full result in map for click handler (need 'term' for lazy search)
                 self.analysis_results_map[row_idx] = res
                 
                 # Use exact mapping
                 item_id = self.excel_row_to_item_id.get(row_idx)
                 
                 if item_id:
                     if found:
                         self.rule_tree.set(item_id, "status", "✔") # Status column
                         self.rule_tree.item(item_id, tags=('found',))
                     else:
                         self.rule_tree.set(item_id, "status", "")
                         self.rule_tree.item(item_id, tags=('not_found',))
             
             self.rule_tree.tag_configure('found', foreground='#00FF00') # Green
             
             # messagebox.showinfo("Success", status_msg) # Don't popup on success, just status bar. user wants speed.
        else:
             self.status_label.configure(text="Error occurred", text_color="red")
             messagebox.showerror("Error", status_msg)

    def load_rule_table(self, file_path):
        # Clear existing
        for item in self.rule_tree.get_children():
            self.rule_tree.delete(item)
        self.analysis_results_map = {}
        self.row_data_map = {}
        self.excel_row_to_item_id = {} # Map Excel Row ID -> Tree Item ID
        self.item_id_to_excel_row = {} # Map Tree Item ID -> Excel Row ID
            
        try:
            wb = openpyxl.load_workbook(file_path, data_only=True)
            sheet = wb.active # Assuming first sheet
            
            # Iterate from row 2 (skip header)
            # Use values_only=False to get row objects and exact row numbers
            for row in sheet.iter_rows(min_row=2):
                if not row:
                    continue
                
                # Check if row is empty of values
                if all(c.value is None for c in row):
                    continue
                    
                row_idx = row[0].row # Accurate Excel Row ID
                
                # Cache full data (extract values from cells)
                row_values = [c.value for c in row]
                self.row_data_map[row_idx] = row_values
                
                # Display first two columns
                ref = row_values[0] if len(row_values) > 0 and row_values[0] else ""
                val = row_values[1] if len(row_values) > 1 and row_values[1] else ""
                
                # Insert and map
                item_id = self.rule_tree.insert("", "end", values=("🔍", ref, val, ""))
                
                self.excel_row_to_item_id[row_idx] = item_id
                self.item_id_to_excel_row[item_id] = row_idx
                
        except PermissionError:
            messagebox.showerror("Error", f"Dosya açık olabilir: {os.path.basename(file_path)}\nLütfen dosyayı kapatıp tekrar deneyin.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load Excel: {e}")

    def on_table_click(self, event):
        item_id = self.rule_tree.identify_row(event.y)
        column_id = self.rule_tree.identify_column(event.x)
        
        if not item_id:
            return
            
        # Get Excel Row Index from Map
        row_index_excel = self.item_id_to_excel_row.get(item_id)
        
        if not row_index_excel:
            return

        # Check if clicked on "view" column
        if column_id == "#1":
            # Open Detail Window with FULL data
            full_data = self.row_data_map.get(row_index_excel, ())
            self.open_detail_window(full_data, row_index_excel)
            return # Do not jump to PDF

        # If not view column, proceed to PDF Jump
        
        result = self.analysis_results_map.get(row_index_excel)
        if result and result.get("found"):
            locations = result.get("locations", [])
            if locations:
                first_loc = locations[0]
                
                # Check for Lazy Load (rect is None)
                if first_loc["rect"] is None:
                    try:
                        page_num = first_loc["page"]
                        term = result["term"]
                        # Normalize term: split and join to handle newlines/excess spaces
                        # This matches the logic used in analysis_engine pre-check
                        term_norm = " ".join(str(term).split())
                        
                        if self.pdf_renderer.doc:
                            page = self.pdf_renderer.doc.load_page(page_num)
                            
                            # Debug Log
                            with open("debug_log.txt", "a", encoding="utf-8") as f:
                                f.write(f"\n--- Click Row ---\nTerm: '{term}'\nNorm: '{term_norm}'\nPage: {page_num}\n")

                            # 1. Try Exact/Normalized Search First (Fastest)
                            # PyMuPDF search_for is case-insensitive by default, but let's be sure.
                            found_rects = page.search_for(term) 
                            if not found_rects:
                                found_rects = page.search_for(term_norm)
                                
                            if found_rects:
                                r = found_rects[0]
                                first_loc["rect"] = [r.x0, r.y0, r.x1, r.y1]
                                with open("debug_log.txt", "a", encoding="utf-8") as f: f.write(f"Found via search_for: {first_loc['rect']}\n")
                            else:
                                # 2. Fallback: Word Sequence Search (Robust for newlines/spacing/punctuation)
                                search_words = term_norm.lower().split()
                                if search_words:
                                    page_words = page.get_text("words") # list of (x0,y0,x1,y1, "word", block, line, word_no)
                                    
                                    # Find all occurrences of the first word (allow substring for punctuation e.g. "word," matches "word")
                                    candidate_indices = [i for i, w in enumerate(page_words) if search_words[0] in w[4].lower()]
                                    
                                    with open("debug_log.txt", "a", encoding="utf-8") as f: f.write(f"Candidates indices: {candidate_indices}\n")
                                    
                                    for start_idx in candidate_indices:
                                        # Check if subsequent words match
                                        if start_idx + len(search_words) > len(page_words):
                                            continue
                                            
                                        match = True
                                        matched_rects = []
                                        
                                        for i, sw in enumerate(search_words):
                                            pw = page_words[start_idx + i]
                                            # Robust check: substring match
                                            if sw not in pw[4].lower(): 
                                                match = False
                                                break
                                            
                                            # Collect rect (x0, y0, x1, y1)
                                            matched_rects.append(fitz.Rect(pw[0], pw[1], pw[2], pw[3]))
                                            
                                        if match:
                                            # Found! Combine rects.
                                            final_rect = matched_rects[0]
                                            for r in matched_rects[1:]:
                                                final_rect |= r # Union of rects
                                            
                                            first_loc["rect"] = [final_rect.x0, final_rect.y0, final_rect.x1, final_rect.y1]
                                            with open("debug_log.txt", "a", encoding="utf-8") as f: f.write(f"Found via word search: {first_loc['rect']}\n")
                                            break # Stop after first match
                    except Exception as e:
                        print(f"Error lazy loading rect: {e}")
                        with open("debug_log.txt", "a", encoding="utf-8") as f: f.write(f"Error: {e}\n")
                
                # ALWAYS Jump to page, even if rect is None
                self.current_page = first_loc["page"]
                rect = first_loc.get("rect")
                
                if rect:
                    self.show_page(self.current_page, highlight_rect=rect)
                else:
                    # Show page without highlight and warn
                    self.show_page(self.current_page)
                    messagebox.showwarning("Highlight Failed", f"Item found on Page {self.current_page + 1}, but exact text location could not be highlighted.\n\nTerm: {result.get('term')}")
                
                self.update_nav_buttons()

    def open_detail_window(self, data, row_index):
        if not data:
            return
            
        # Format data string
        # Side-by-side format: [A] Val1  |  [B] Val2  |  [C] Val3
        display_parts = []
        for i, val in enumerate(data):
            col_letter = chr(65 + i) if i < 26 else f"Col{i}" 
            val_str = str(val) if val is not None else ""
            display_parts.append(f"[{col_letter}] {val_str}")
            
        display_text = "  |  ".join(display_parts)
        
        # Check if window already exists
        if hasattr(self, 'detail_window') and self.detail_window is not None and self.detail_window.winfo_exists():
            self.detail_window.lift() # Bring to front
            self.detail_window.focus_force() # Focus to catch events
            # Update content
            self.detail_ref_label.configure(text=f"Row {row_index} Details")
            self.detail_text_box.configure(state="normal")
            self.detail_text_box.delete("0.0", "end")
            self.detail_text_box.insert("0.0", display_text)
            self.detail_text_box.configure(state="disabled")
            return

        # Create new window
        self.detail_window = ctk.CTkToplevel(self)
        self.detail_window.title(f"Row {row_index} Details")
        self.detail_window.geometry("1000x200") # Wider, less height
        self.detail_window.attributes("-topmost", True) # Keep on top
        
        # Bind Auto-Close events
        self.detail_window.bind("<FocusOut>", self.close_detail_window)
        self.detail_window.bind("<Key>", self.close_detail_window)
        
        self.detail_ref_label = ctk.CTkLabel(self.detail_window, text=f"Row {row_index} Details", font=ctk.CTkFont(size=14, weight="bold"))
        self.detail_ref_label.pack(padx=20, pady=(20, 10), fill="x")
        
        # Use Textbox to allow scrolling if content is very wide, but keep it one line if possible? 
        # Textbox wraps by default. We can disable wrap to force horizontal scrolling or let it wrap if huge.
        # "yan yana olsun" usually implies one long line or wrapping.
        # Let's keep wrap="word" so it doesn't hide content, but with 1000px width it should fit most.
        self.detail_text_box = ctk.CTkTextbox(self.detail_window, wrap="word", height=100)
        self.detail_text_box.pack(padx=20, pady=(0, 20), fill="both", expand=True)
        
        self.detail_text_box.insert("0.0", display_text)
        self.detail_text_box.configure(state="disabled") # Read-only
        
        # Force focus so FocusOut can trigger later
        self.detail_window.focus_force()

    # ... (existing code) ...

    def close_detail_window(self, event=None):
        if hasattr(self, 'detail_window') and self.detail_window:
            self.detail_window.destroy()
            self.detail_window = None

    def load_latest_data(self):
        # 1. Search for latest Excel and PDF in root and Talepler
        import glob
        
        search_dirs = [".", "Talepler"]
        
        # Find latest Excel
        latest_excel = None
        latest_excel_time = 0
        
        # Find latest PDF
        latest_pdf = None
        latest_pdf_time = 0
        
        for d in search_dirs:
            # Excel
            for f in glob.glob(os.path.join(d, "*.xlsx")):
                try:
                    mtime = os.path.getmtime(f)
                    if mtime > latest_excel_time:
                        latest_excel_time = mtime
                        latest_excel = f
                except: pass
                
            # PDF
            for f in glob.glob(os.path.join(d, "*.pdf")):
                try:
                    mtime = os.path.getmtime(f)
                    if mtime > latest_pdf_time:
                        latest_pdf_time = mtime
                        latest_pdf = f
                except: pass
                
        # 2. Load them
        loaded_excel = False
        loaded_pdf = False
        
        if latest_excel:
            self.full_rule_path = os.path.abspath(latest_excel)
            self.selected_rule_path_label.configure(text=os.path.basename(latest_excel), text_color=("gray10", "gray90"))
            self.load_rule_table(self.full_rule_path)
            loaded_excel = True
            
        if latest_pdf:
             # Try to load to verify it's a valid PDF and accessible
            if self.pdf_renderer.load_pdf(latest_pdf):
                self.selected_control_path_label.configure(text=latest_pdf, text_color="black")
                self.full_control_path = os.path.abspath(latest_pdf)
                
                # Show first page
                self.current_page = 0
                self.total_pages = len(self.pdf_renderer.doc)
                self.show_page(self.current_page)
                self.update_nav_buttons()
                loaded_pdf = True
            else:
                messagebox.showwarning("Warning", f"Latest PDF found but failed to open:\n{latest_pdf}")

        # Feedback
        if loaded_excel and loaded_pdf:
            self.status_label.configure(text="Loaded latest data successfully.", text_color="green")
        elif loaded_excel:
            self.status_label.configure(text="Loaded Excel only. No PDF found.", text_color="orange")
        elif loaded_pdf:
             self.status_label.configure(text="Loaded PDF only. No Excel found.", text_color="orange")
        else:
             messagebox.showinfo("Info", "No suitable Excel or PDF files found in project folders.")

    def select_rule_file(self):

        filetypes = (
            ('All files', '*.*'),
            ('Excel files', '*.xlsx'),
            ('PDF files', '*.pdf'),
            ('Word files', '*.docx')
        )
        filename = filedialog.askopenfilename(title='Open Rule Document', initialdir='/', filetypes=filetypes)
        if filename:
            self.full_rule_path = filename
            self.selected_rule_path_label.configure(text=os.path.basename(filename), text_color=("gray10", "gray90"))
            self.load_rule_table(filename)

    def select_control_file(self):
        filetypes = (('PDF files', '*.pdf'),)
        filename = filedialog.askopenfilename(title='Open Control PDF', initialdir='/', filetypes=filetypes)
        if filename:
            # Try to load to verify it's a valid PDF and accessible
            if self.pdf_renderer.load_pdf(filename):
                self.selected_control_path_label.configure(text=filename, text_color="black")
                self.full_control_path = filename # Store full path
                
                # Show first page
                self.current_page = 0
                self.total_pages = len(self.pdf_renderer.doc)
                self.show_page(self.current_page)
                self.update_nav_buttons()
            else:
                 # Check if it was a permission issue? 
                 # load_pdf returns False on error. 
                 # We can try to open it here just to check permission and show message
                try:
                    marker_file = open(filename, 'rb')
                    marker_file.close()
                    # If we got here, it might be corrupt, not permission.
                    messagebox.showerror("Error", "Failed to load PDF. File might be corrupt.")
                except PermissionError:
                    messagebox.showerror("Error", f"Dosya açık olabilir: {os.path.basename(filename)}\nLütfen dosyayı kapatıp tekrar deneyin.")
                except Exception:
                     messagebox.showerror("Error", "Failed to load PDF.")

    def show_page(self, page_num, highlight_rect=None):
        img = self.pdf_renderer.get_new_page_image(page_num, display_width=self.main_frame.winfo_width(), display_height=self.main_frame.winfo_height())
        
        # If we have a highlight rect, we need to draw it. 
        # Since ctk.CTkImage is a wrapper, we should probably draw on the PIL image BEFORE creating CTkImage.
        # But get_new_page_image creates it. 
        # Option A: Modify get_new_page_image to accept highlight_rect.
        # Option B: Re-implement image generation here using PDFRenderer's internals (less clean).
        # Let's modify PDFRenderer to support generic overlay drawing or pass a callback?
        # Simpler: Modify get_new_page_image in pdf_renderer.py to accept optional highlight rect.
        # OR: Do it here if I have the PIL image. 
        # get_new_page_image returns CTkImage. I can't easily modify the internal PIL image of a CTkImage.
        # So I must pass the highlight request to `pdf_renderer`.
        # For this step, I will modify `pdf_renderer.py` as well.
        # But I'm in this file now. I'll pass `highlight_rect` to `get_new_page_image`. 
        # I need to update `pdf_renderer.py` concurrently or next.
        
        # Let's assume I will update `pdf_renderer.py` to accept `highlight_rect`.
        img = self.pdf_renderer.get_new_page_image(page_num, display_width=self.main_frame.winfo_width(), display_height=self.main_frame.winfo_height(), highlight_rect=highlight_rect)
        
        if img:
            self.pdf_display_label.configure(image=img, text="")
            self.page_label.configure(text=f"Page {page_num + 1} of {self.total_pages}")
    
    def next_page(self):
        if self.current_page < self.total_pages - 1:
            self.current_page += 1
            self.show_page(self.current_page)
            self.update_nav_buttons()
            
    def prev_page(self):
        if self.current_page > 0:
            self.current_page -= 1
            self.show_page(self.current_page)
            self.update_nav_buttons()

    def update_nav_buttons(self):
        self.prev_btn.configure(state="normal" if self.current_page > 0 else "disabled")
        self.next_btn.configure(state="normal" if self.current_page < self.total_pages - 1 else "disabled")
