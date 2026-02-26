"""
Image Analysis Engine for Kutu Tasarım Kontrolü.

Supports:
  - PDF files:  text extracted via PyMuPDF (fitz) or PaddleOCR for artwork PDFs
  - PNG / JPG:  text extracted via PaddleOCR (or Tesseract as fallback)

Result per row:
    {
        "row_index": int,
        "found":     bool,
        "matched_term": str,
        "rect":      [x0, y0, x1, y1] in PIXEL coords (of the rendered image),
        "term":      str,   # original search term
    }
"""

import os
import sys
import re
import fitz          # PyMuPDF
import openpyxl
from PIL import Image


# ---------------------------------------------------------------------------
# Optional OCR imports
# ---------------------------------------------------------------------------
try:
    import pytesseract
    # Verify binary actually works
    pytesseract.get_tesseract_version()
    _TESSERACT_AVAILABLE = True
except Exception:
    _TESSERACT_AVAILABLE = False

try:
    _stderr = sys.stderr
    sys.stderr = open(os.devnull, 'w')
    try:
        from paddleocr import PaddleOCR as _PaddleOCR
        _PADDLE_AVAILABLE = True
    finally:
        sys.stderr = _stderr
except Exception:
    _PADDLE_AVAILABLE = False

_paddle_instance = None
def _get_paddle():
    global _paddle_instance
    if _paddle_instance is None:
        import logging
        logging.disable(logging.CRITICAL)
        try:
            _paddle_instance = _PaddleOCR()
        except Exception:
            _paddle_instance = _PaddleOCR(lang='en')
        finally:
            logging.disable(logging.NOTSET)
    return _paddle_instance


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _normalize(text: str) -> str:
    """Lower-case and collapse whitespace."""
    return " ".join(str(text).lower().split())


def _lenient(text: str) -> str:
    """Lowercase + replace ALL punctuation with spaces (for fuzzy matching)."""
    t = str(text).lower()
    t = re.sub(r'[^\w\s]', ' ', t, flags=re.UNICODE)
    return ' '.join(t.split())


def _words_from_pdf_page(page, zoom: float = 2.0):
    """
    Returns list of dicts:
        { text, x0, y0, x1, y1 }
    Coordinates are in PIXEL space at the given zoom.
    """
    words_raw = page.get_text("words")   # (x0,y0,x1,y1, "word", block, line, word_no)
    result = []
    for w in words_raw:
        result.append({
            "text": w[4],
            "x0": w[0] * zoom,
            "y0": w[1] * zoom,
            "x1": w[2] * zoom,
            "y1": w[3] * zoom,
        })
    return result


def _words_from_image_ocr(pil_image):
    """
    Returns list of dicts: { text, x0, y0, x1, y1 }
    Uses Tesseract via pytesseract.image_to_data.
    Coordinates are in pixel space of the PIL image.
    """
    if not _TESSERACT_AVAILABLE:
        raise RuntimeError(
            "pytesseract kurulu değil.\n"
            "Kurulum: pip install pytesseract\n"
            "Ardından Tesseract-OCR programını kurun: https://github.com/UB-Mannheim/tesseract/wiki"
        )

    from PIL import ImageEnhance, ImageFilter

    # Artwork görüntüleri için ön işleme: gri + kontrast artır
    # Bu Tesseract'ın renkli/karmaşık arka planlarda çalışmasını iyileştirir
    img = pil_image.convert("L")                          # gri tonlama
    img = ImageEnhance.Contrast(img).enhance(2.0)        # kontrast 2x
    img = img.filter(ImageFilter.SHARPEN)                # keskinleştir
    img = img.convert("RGB")

    config = "--oem 3 --psm 11"  # psm 11 = sparse text (artwork uyumlu)

    data = pytesseract.image_to_data(
        img,
        lang="tur+eng",
        config=config,
        output_type=pytesseract.Output.DICT
    )
    result = []
    n = len(data["text"])
    for i in range(n):
        txt = data["text"][i].strip()
        conf_raw = data["conf"][i]
        # conf==-1: yapısal token (sayfa/blok sınırı) → atla
        # conf>=0: gerçek kelime → eşik yok, hepsini al
        try:
            conf = int(conf_raw)
        except (ValueError, TypeError):
            conf = -1
        if not txt or conf == -1:
            continue
        x = data["left"][i]
        y = data["top"][i]
        w = data["width"][i]
        h = data["height"][i]
        result.append({
            "text": txt,
            "x0": float(x),
            "y0": float(y),
            "x1": float(x + w),
            "y1": float(y + h),
        })
    return result


def _words_from_paddle_ocr(pil_image):
    """
    Extract words using PaddleOCR.
    Returns list of dicts: { text, x0, y0, x1, y1 }
    """
    import numpy as np
    img_np = np.array(pil_image)
    paddle = _get_paddle()

    # Yeni PaddleOCR API: .predict() veya eski .ocr() (cls olmadan)
    try:
        result = paddle.predict(img_np)
    except Exception:
        try:
            result = paddle.ocr(img_np)
        except Exception:
            return []

    words = []
    if not result:
        return words
    for line_group in result:
        if not line_group:
            continue
        # result elemanı (box, (text, conf)) veya dict olabilir
        for line in line_group:
            try:
                if isinstance(line, dict):
                    # yeni format: {'transcription': ..., 'points': ...}
                    text = line.get('transcription', line.get('text', ''))
                    points = line.get('points', line.get('bbox', []))
                    if points and len(points) >= 2:
                        xs = [p[0] if isinstance(p, (list, tuple)) else p for p in points]
                        ys = [p[1] if isinstance(p, (list, tuple)) else 0 for p in points]
                    else:
                        continue
                else:
                    box, (text, conf) = line
                    xs = [p[0] for p in box]
                    ys = [p[1] for p in box]
                if not text or not text.strip():
                    continue
                words.append({
                    "text": text.strip(),
                    "x0": float(min(xs)),
                    "y0": float(min(ys)),
                    "x1": float(max(xs)),
                    "y1": float(max(ys)),
                })
            except Exception:
                continue
    return words

def _search_in_words(words, search_term: str):
    """
    Robust word search handling substrings and varying spaces.
    Returns (matched_text, rect_dict) or (None, None).
    """
    if not words:
        return None, None

    # Helper to calculate bounding box of a list of words
    def _make_result(span):
        if not span: return None, None
        x0 = min(w["x0"] for w in span)
        y0 = min(w["y0"] for w in span)
        x1 = max(w["x1"] for w in span)
        y1 = max(w["y1"] for w in span)
        return " ".join(w["text"] for w in span), {"x0": x0, "y0": y0, "x1": x1, "y1": y1}

    # 1. Tam Eşleşme (Full Text) veya "Contains" Araması
    # Bütün kelimeleri tek boşlukla birleştir ve her karakterin hangi kelimeye ait olduğunu kaydet.
    full_text = ""
    char_to_word = []
    
    for w in words:
        t = w["text"]
        full_text += t + " "
        char_to_word.extend([w] * len(t))
        char_to_word.append(None) # Boşluk için
        
    full_text_lower = full_text.lower()
    needle_lower = search_term.strip().lower()

    if needle_lower in full_text_lower:
        pos = full_text_lower.find(needle_lower)
        matched_words = []
        for i in range(pos, pos + len(needle_lower)):
            w = char_to_word[i]
            if w is not None and (not matched_words or matched_words[-1] != w):
                matched_words.append(w)
        if matched_words:
            return _make_result(matched_words)

    # 2. Esnek (Lenient) Substring Araması (Boşluksuz ve Noktalamasız)
    # Tasarımda araya virgül vs. girmiş olabilir.
    expanded = []
    for w in words:
        parts = _lenient(w["text"]).split()
        for part in parts:
            expanded.append((part, w))
            
    needle_lenient = _lenient(search_term).split()
    if needle_lenient and expanded:
        needle_ns = "".join(needle_lenient) # "humanissağlıkaş"
        if needle_ns:
            concat_str = ""
            tok_starts = []
            for tok, w in expanded:
                tok_starts.append((len(concat_str), w))
                concat_str += tok

            pos = concat_str.find(needle_ns)
            if pos != -1:
                end_pos = pos + len(needle_ns)
                match_words = []
                for (start_idx, w) in tok_starts:
                    if start_idx >= pos and start_idx < end_pos:
                        if not match_words or match_words[-1] != w:
                            match_words.append(w)
                if match_words:
                    return _make_result(match_words)

    # 3. Kelime Kelime Ayrı Ayrı İçerme (Unordered Contains)
    # Eğer uzun cümlenin parçaları farklı yerlerde ise bulmaya çalış
    needle_strict = _normalize(search_term).split()
    found_spans = []
    word_strict = [_normalize(w["text"]) for w in words]
    
    for nw in needle_strict:
        nw_l = _lenient(nw)
        for i, wt in enumerate(word_strict):
            wt_l = _lenient(wt)
            if (nw and nw in wt) or (nw_l and wt_l and (nw_l in wt_l or wt_l in nw_l)):
                found_spans.append(words[i])
                break

    if len(found_spans) == len(needle_strict):
        return _make_result(found_spans)

    return None, None



# ---------------------------------------------------------------------------
# Main Engine
# ---------------------------------------------------------------------------

class ImageAnalysisEngine:

    RENDER_ZOOM = 2.0  # PDF render zoom for display & coord mapping

    def __init__(self):
        self.image = None          # PIL.Image — the rendered/loaded image
        self.words = []            # list of word dicts (from PDF or OCR)
        self.file_path = None
        self.file_type = None      # "pdf" | "image"

    # ------------------------------------------------------------------
    # Loading
    # ------------------------------------------------------------------

    def load_file(self, path: str):
        """
        Load a PDF (first page rendered) or image file.
        Returns (success: bool, error_msg: str).
        """
        ext = os.path.splitext(path)[1].lower()
        self.file_path = path
        self.image = None
        self.words = []

        if ext == ".pdf":
            return self._load_pdf(path)
        elif ext in (".png", ".jpg", ".jpeg", ".bmp", ".tiff", ".tif", ".webp"):
            return self._load_image(path)
        else:
            return False, f"Desteklenmeyen dosya formatı: {ext}"

    def _load_pdf(self, path):
        try:
            doc = fitz.open(path)

            # Görüntü için sayfa 0'ı render et (display zoom)
            page0 = doc.load_page(0)
            mat = fitz.Matrix(self.RENDER_ZOOM, self.RENDER_ZOOM)
            pix = page0.get_pixmap(matrix=mat)
            self.image = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)

            # --- Kelime çıkarma stratejisi ---
            # Sadece fitz metin katmanını kaydet.
            # PaddleOCR veya Tesseract gibi yavaş işlemler,
            # kullanıcı "Analizi Başlat" dediğinde `run_analysis` içinde yapılacak.
            all_words_text = []
            for page_num in range(len(doc)):
                p = doc.load_page(page_num)
                all_words_text.extend(_words_from_pdf_page(p, zoom=self.RENDER_ZOOM))

            self.words = all_words_text

            self.file_type = "pdf"
            self._doc = doc
            self._page = page0
            return True, ""
        except Exception as e:
            return False, str(e)



    def _load_image(self, path):
        try:
            self.image = Image.open(path).convert("RGB")
            self.file_type = "image"
            # Words extracted lazily during analysis (OCR is slow)
            return True, ""
        except Exception as e:
            return False, str(e)

    # ------------------------------------------------------------------
    # Analysis
    # ------------------------------------------------------------------

    def run_analysis(self, rule_path: str, region=None):
        """
        Run analysis against loaded file using rules from Excel.
        region: optional (x0, y0, x1, y1) in pixel coords of the rendered image.
                If given, only words within that rectangle are searched.
        Returns list of result dicts. Raises on error.
        """
        if self.image is None:
            raise RuntimeError("Önce bir tasarım dosyası yükleyin.")

        # Ensure OCR / word list is ready
        # Eğer PDF'te >150 kelime yoksa (artwork vs) veya görüntü ise PaddleOCR çalıştır
        if self.file_type == "image":
            if not self.words:
                self.words = _words_from_image_ocr(self.image)
        elif self.file_type == "pdf":
            # self.words şu an fitz ile alınan metni taşıyor (_load_pdf'te atandı)
            # Eğer fitz'in bulduğu kelime sayısı azsa (<150) OCR yapıp ikisini BİRLEŞTİRİYORUZ.
            # Önceden OCR sonucunu fitz sonucunun üzerine yazıyorduk, bu da vektörel PDF'lerde 
            # düzgün metinlerin kaybolmasına neden oluyordu!
            if len(self.words) < 150 and getattr(self, "_ocr_done", False) is False:
                self._ocr_done = True
                # O zaman şimdi (analiz başladığında) OCR yap
                all_words_ocr = []
                OCR_ZOOM = 3.0
                for page_num in range(len(self._doc)):
                    p = self._doc.load_page(page_num)
                    mat_ocr = fitz.Matrix(OCR_ZOOM, OCR_ZOOM)
                    pix_ocr = p.get_pixmap(matrix=mat_ocr)
                    page_img = Image.frombytes("RGB",
                                              [pix_ocr.width, pix_ocr.height],
                                              pix_ocr.samples)
                    scale = self.RENDER_ZOOM / OCR_ZOOM
                    try:
                        if _PADDLE_AVAILABLE:
                            ocr_words = _words_from_paddle_ocr(page_img)
                        elif _TESSERACT_AVAILABLE:
                            ocr_words = _words_from_image_ocr(page_img)
                        else:
                            ocr_words = []
                        for w in ocr_words:
                            w["x0"] *= scale
                            w["y0"] *= scale
                            w["x1"] *= scale
                            w["y1"] *= scale
                        all_words_ocr.extend(ocr_words)
                    except Exception:
                        pass
                        
                # Vektörel metinleri kaybetmemek için OCR sonuçlarını mevcut self.words'e EKLİYORUZ.
                if all_words_ocr:
                    self.words.extend(all_words_ocr)

        # --- DEBUG LOG BAŞLANGICI ---
        debug_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "debug_kutu.txt")
        dbg_text = []
        dbg_text.append(f"TOTAL WORDS BEFORE REGION: {len(self.words)}")
        if region:
            rx0, ry0, rx1, ry1 = region
            dbg_text.append(f"REGION SELECTED: x0={rx0}, y0={ry0}, x1={rx1}, y1={ry1}")
            if self.words:
                dbg_text.append(f"FIRST WORD COORDS: x0={self.words[0]['x0']}, y0={self.words[0]['y0']}")
            
            words = []
            for w in self.words:
                # Check for intersection between word rect and region rect
                ix_x = w["x0"] <= rx1 and w["x1"] >= rx0
                ix_y = w["y0"] <= ry1 and w["y1"] >= ry0
                if ix_x and ix_y:
                    words.append(w)
            dbg_text.append(f"TOTAL WORDS AFTER REGION: {len(words)}")
        else:
            dbg_text.append("NO REGION SELECTED.")
            words = self.words

        results = []
        rules = self._load_rules(rule_path)

        # --- LOG YAZMA ---
        with open(debug_path, "w", encoding="utf-8") as dbg:
            dbg.write("\n".join(dbg_text) + "\n\n")
            dbg.write(f"=== PDF kelimeleri (ilk 60) ===\n")
            for w in words[:60]:
                dbg.write(f"  '{w['text']}'\n")
            dbg.write(f"\n=== Arama sonuçları ===\n")

            for row_index, search_term in rules:
                if not search_term:
                    continue
                matched_text, rect_dict = _search_in_words(words, str(search_term))
                dbg.write(f"\nArama: '{search_term}'\n")
                dbg.write(f"  normalize: '{_normalize(str(search_term))}'\n")
                dbg.write(f"  lenient:   '{_lenient(str(search_term))}'\n")
                dbg.write(f"  Sonuç: {'BULUNDU → ' + matched_text if matched_text else 'BULUNAMADI'}\n")
                if matched_text and rect_dict:
                    results.append({
                        "row_index": row_index,
                        "found": True,
                        "matched_term": matched_text,
                        "term": str(search_term),
                        "rect": [rect_dict["x0"], rect_dict["y0"],
                                  rect_dict["x1"], rect_dict["y1"]],
                    })
                else:
                    results.append({
                        "row_index": row_index,
                        "found": False,
                        "matched_term": "",
                        "term": str(search_term),
                        "rect": None,
                    })

        return results


    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _load_rules(self, rule_path: str):
        """
        Read Excel rule file.
        Returns list of (row_index, search_term).
        Column A = label/ref, Column B = search term (value to find in design).
        If only column A, use column A as search term.
        """
        wb = openpyxl.load_workbook(rule_path, data_only=True)
        sheet = wb.active
        rules = []
        for row in sheet.iter_rows(min_row=2):
            if all(c.value is None for c in row):
                continue
            row_index = row[0].row
            col_a = row[0].value
            col_b = row[1].value if len(row) > 1 else None
            # Use col B as search term; fall back to col A
            search_term = col_b if col_b is not None else col_a
            rules.append((row_index, search_term))
        return rules

    @property
    def tesseract_available(self):
        return _TESSERACT_AVAILABLE
