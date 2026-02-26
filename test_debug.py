import sys, os
sys.path.insert(0, r'c:\Users\vande\Desktop\Tasarım_Kontrol')

import fitz
from PIL import Image
import numpy as np

pdf_path = r'c:\Users\vande\Desktop\Tasarım_Kontrol\3-Kutu_Tasarım_Kontrolu\Kutu Tedarikçisinden Gelen Örnek Artwork.pdf'
doc = fitz.open(pdf_path)
page = doc.load_page(0)
mat = fitz.Matrix(3, 3)
pix = page.get_pixmap(matrix=mat)
img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
img_np = np.array(img)

outfile = r'c:\Users\vande\Desktop\Tasarım_Kontrol\debug_kutu.txt'
with open(outfile, 'w', encoding='utf-8') as f:
    try:
        import easyocr
        reader = easyocr.Reader(['tr', 'en'], gpu=False)
        results = reader.readtext(img_np)
        f.write(f'EasyOCR buldu: {len(results)} metin\n\n')
        for bbox, text, conf in results:
            xs = [p[0] for p in bbox]
            ys = [p[1] for p in bbox]
            f.write(f'  conf={conf:.2f} text={text!r}\n')
    except Exception as ex:
        import traceback
        f.write(f'HATA: {ex}\n{traceback.format_exc()}')

print('Yazildi')
