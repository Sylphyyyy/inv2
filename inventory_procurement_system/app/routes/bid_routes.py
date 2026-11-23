import pytesseract
import pdfplumber
import re
from pdf2image import convert_from_path

pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

def parse_bid_document(file_path):
    extracted_items = []
    
    try:
        # 1. Try digital text extraction first using pdfplumber
        with pdfplumber.open(file_path) as pdf:
            for page_num, page in enumerate(pdf.pages):
                text = page.extract_text(layout=True) or page.extract_text()
                
                # 2. Fallback to Tesseract OCR if a page returns no text (scanned image page)
                if not text or not text.strip():
                    try:
                        # Convert specific PDF page to an image for OCR processing
                        page_image = page.to_image(resolution=300).original
                        text = pytesseract.image_to_string(page_image, lang='eng')
                    except Exception as ocr_err:
                        print(f"[WARNING] OCR fallback failed for page {page_num + 1}: {ocr_err}")
                
                print(f"\n--- PAGE {page_num + 1} PROCESSED TEXT ---")
                print(text if text else "[NO TEXT FOUND]")
                print("----------------------------\n")
                
                if not text:
                    continue
                
                # Highly relaxed fallback matching
                lines = text.split('\n')
                for line in lines:
                    match = re.search(r'(?:\b|^)(\d{1,4})\s*(pcs|pc|units|unit|box|boxes|sets|set|reams|ream|lot|lots)?\b\s*(.*)', line, re.IGNORECASE)
                    if match:
                        qty = int(match.group(1))
                        unit = match.group(2) or "units"
                        desc = match.group(3).strip()
                        
                        # Filter out dates or purely numeric lines
                        if desc and len(desc) > 3 and not re.search(r'202[0-9]', line):
                            extracted_items.append({
                                'item_name': desc[:100],  # Limit length
                                'quantity': qty,
                                'unit': unit
                            })
                            
    except Exception as e:
        print(f"[ERROR] Failed to parse document: {e}")
        
    return extracted_items
