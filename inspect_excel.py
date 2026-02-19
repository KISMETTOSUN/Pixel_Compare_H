import openpyxl
import os

file_path = "c:\\Users\\vande\\Desktop\\Humanis\\Kural.xlsx"
if os.path.exists(file_path):
    try:
        wb = openpyxl.load_workbook(file_path)
        sheet = wb.active
        print(f"Sheet Name: {sheet.title}")
        print("First 5 rows:")
        for row in sheet.iter_rows(min_row=1, max_row=5, values_only=True):
            print(row)
    except Exception as e:
        print(f"Error reading excel: {e}")
else:
    print("File not found")
