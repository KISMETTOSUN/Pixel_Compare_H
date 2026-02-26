import sys
import os

from utils.image_analysis_engine import ImageAnalysisEngine

def test_kutu():
    engine = ImageAnalysisEngine()
    
    # PDF'yi bul
    pdf_path = None
    for f in os.listdir("."):
        if f.lower().endswith(".pdf"):
            pdf_path = f
            break
            
    if not pdf_path:
        print("PDF bulunamadı")
        return
        
    print(f"Loading {pdf_path}...")
    engine.load_file(pdf_path)
    print(f"Loaded. Words: {len(engine.words)}")
    
    # Excel bul
    excel_path = None
    for f in os.listdir("."):
        if f.lower().endswith(".xlsx"):
            excel_path = f
            break
            
    if excel_path:
        print(f"Running analysis with {excel_path}...")
        results = engine.run_analysis(excel_path)
        for r in results:
            print(f"Row {r['row_index']} - {r['term']} -> Found: {r['found']} Match: {r['matched_term']}")

if __name__ == '__main__':
    test_kutu()
