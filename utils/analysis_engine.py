import fitz  # PyMuPDF
import openpyxl
import os
import difflib

class AnalysisEngine:
    def __init__(self):
        pass

    def extract_text_from_pdf(self, pdf_path):
        """Extracts text from PDF and returns a list of lines."""
        lines = []
        try:
            doc = fitz.open(pdf_path)
            for page in doc:
                text = page.get_text("text")
                # Split by newline and filter empty lines
                page_lines = [line.strip() for line in text.split('\n') if line.strip()]
                lines.extend(page_lines)
            return lines
        except Exception as e:
            print(f"Error reading PDF: {e}")
            return []

    def run_analysis(self, rule_excel_path, control_pdf_path):
        """
        Reads Excel (Sheet1).
        Column B: Search Term.
        Search in PDF using page.search_for() to get coordinates.
        Returns a dict: {"status": str, "results": list of dicts}
        Each result dict: {"row": int, "found": bool, "locations": list of dicts}
        Location dict: {"page": int, "rect": [x0, y0, x1, y1]}
        """
        # Alias arguments to match internal usage
        rule_path = rule_excel_path
        control_path = control_pdf_path

        if not os.path.exists(rule_path) or not os.path.exists(control_path):
            return {"status": "Error: File not found.", "results": []}

        try:
            # Load Excel
            try:
                workbook = openpyxl.load_workbook(rule_path)
            except PermissionError:
                return {"status": f"Error: Rule file is open: {os.path.basename(rule_path)}. Please close it.", "results": []}

            if "Sheet1" not in workbook.sheetnames:
                return {"status": "Error: 'Sheet1' not found in Excel file.", "results": []}
            
            sheet = workbook["Sheet1"]
            
            # Load PDF
            try:
                doc = fitz.open(control_pdf_path)
            except PermissionError:
                return {"status": f"Error: Control PDF file is open: {os.path.basename(control_pdf_path)}. Please close it.", "results": []}
            
            # Optimization: Extract all text once
            # Dict mapping page_num -> text content (lowercase for case-insensitive check if needed, but search_for is case-insensitive usually?)
            # search_for is case-insensitive by default in PyMuPDF? No, it's case-insensitive by default?
            # actually flags=fitz.TEXT_PRESERVE_LIGATURES | ... 
            # Default is case-insensitive? Let's assume we want exact match for now as per previous logic which didn't specify.
            # But to be safe, let's extract text as is.
            page_cache = {} 
            for page_num in range(len(doc)):
                page = doc.load_page(page_num)
                page_cache[page_num] = page.get_text("text") # Cache text
            
            analysis_results = []
            
            # 1. Read Rules from Excel
            # Store in a list of dicts to allow mutable 'found' state and location appending
            rules_data = [] # List of {row_index, term, locations: []}
           
            # Iterate through rows sequentially to preserve order
            # SAFETY VALVE: Stop if we encounter too many consecutive empty rows. 
            # This prevents hanging if Excel thinks UsedRange is huge (e.g. 1 million rows).
            consecutive_empty = 0
            
            for row in sheet.iter_rows(min_row=2, max_col=2): 
                if not row or len(row) < 2:
                     consecutive_empty += 1
                     if consecutive_empty > 20: break
                     continue
                
                cell_b = row[1]
                term = str(cell_b.value).strip() if cell_b.value else ""
                
                if term:
                    consecutive_empty = 0 # Reset counter
                    rules_data.append({
                        "row_index": row[0].row,
                        "term": term,
                        "found": False,
                        "locations": []
                    })
                else:
                    consecutive_empty += 1
                    if consecutive_empty > 20: break
            
            if not rules_data:
                return {"status": "No rules found in Excel.", "results": []}

            # 2. Iterate PDF Pages (Outer Loop)
            # This ensures we load each page only ONCE.
            # OPTIMIZATION: "Lazy Search". 
            # Analysis Phase: Only check IF it exists (using fast string check).
            # Visualization Phase (UI): Will find exact coordinates when clicked.
            
            # 2. Iterate PDF Pages (Outer Loop)
            # FASTEST MODE: Strict "Text Exist" check. 
            # ABSOLUTELY NO coordinate calculations here. 
            # Coordinates are calculated ONLY when user clicks the row in UI.
            
            for page_num in range(len(doc)):
                page = doc.load_page(page_num)
                # Python string 'in' operator is instant.
                # Normalize text: lower case, replace newlines/tabs with spaces, remove duplicate spaces
                raw_text = page.get_text("text") or ""
                # Replace common punctuation with spaces to avoid "word." mismatching "word"
                for p in [".", ",", ":", ";", "(", ")", "-", "\u2013", "\u2014"]:
                    raw_text = raw_text.replace(p, " ")
                
                page_text_norm = " ".join(raw_text.lower().split())
                
                # Debug: Write only first 50 chars of page text to avoid huge log
                with open("debug_analysis_engine.txt", "a", encoding="utf-8") as f:
                    f.write(f"Page {page_num} Norm: {page_text_norm[:100]}...\n")

                # Check ALL rules against this page
                for rule in rules_data:
                    term = rule["term"]
                    
                    # Normalize term similar to page text
                    term_clean = str(term)
                    for p in [".", ",", ":", ";", "(", ")", "-", "\u2013", "\u2014"]:
                        term_clean = term_clean.replace(p, " ")
                    term_norm = " ".join(term_clean.lower().split())
                    
                    # Normalized string existence check
                    if term_norm in page_text_norm:
                        rule["found"] = True
                        rule["locations"].append({
                            "page": page_num,
                            "rect": None # UI will calculate this on click
                        })
                        with open("debug_analysis_engine.txt", "a", encoding="utf-8") as f:
                            f.write(f"  [MATCH] Term: '{term_norm}'\n")
                    else:
                         # Log failures for specific suspicious terms
                         if "500" in term_norm or "tablet" in term_norm:
                             with open("debug_analysis_engine.txt", "a", encoding="utf-8") as f:
                                 f.write(f"  [FAIL] Term: '{term_norm}' not in Page {page_num}\n")
            
            # 3. Return results (rules_data is already in correct format)
            analysis_results = rules_data
            
        except Exception as e:
            return {"status": f"Error during analysis: {e}", "results": []}

        return {"status": "Analysis Complete", "results": analysis_results}
