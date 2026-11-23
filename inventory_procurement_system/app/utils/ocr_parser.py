import os
import json
import time
from pydantic import BaseModel, Field
from typing import List, Literal, Optional

# 1. Define structured output formats for Line Items
class Item(BaseModel):
    item_name: str = Field(description="Product/Service Name")
    quantity: int = Field(description="Exact integer quantity from the Quantity column. Must strip commas.")
    unit: str = Field(description="Unit of measurement from the UOM column (e.g., 'Unit', 'pcs')")
    description: str = Field(description="Full description details of the item")
    price: Optional[float] = Field(
        default=None,
        description="Per-unit price when listed, otherwise the item's extended line total. Leave null if neither is present."
    )
    price_type: Literal['unit', 'line_total', 'missing'] = Field(
        default='unit',
        description="Whether price is a per-unit price, an extended line total, or missing."
    )

# 2. Define structured output format for the Procurement Metadata
class Metadata(BaseModel):
    procurement_title: str = Field(description="Title of the procurement project. Return 'N/A' if missing.")
    abc: float = Field(description="Approved Budget for the Contract (ABC) as a plain float number. Strip all commas and currency signs.")
    pre_bid_conference_date: str = Field(description="Date and Time of Pre-bid Conference. Return 'N/A' if missing.")
    place_of_bidding: str = Field(description="Address or location of the bidding. Return 'N/A' if missing.")
    municipality: str = Field(description="Municipality or City. Return 'N/A' if missing.")
    agency_requested: str = Field(description="Requesting Gov Office or Agency. Return 'N/A' if missing.")

# 3. Combine them into the final expected JSON structure
class ProcurementData(BaseModel):
    metadata: Metadata
    items: List[Item]

def normalize_item_prices(items):
    for item in items:
        quantity = item.get('quantity', 0)
        price_type = item.get('price_type', 'unit')
        if price_type == 'line_total':
            item['price'] = item['price'] / quantity if item.get('price') is not None and quantity > 0 else None
            item['price_type'] = 'calculated' if item['price'] is not None else 'missing'
        elif price_type == 'missing' or item.get('price') is None:
            item['price'] = None
            item['price_type'] = 'missing'
    return items

def extract_text_from_file(file_path: str) -> str:
    """Extract text from PDF or image using existing OCR dependencies.

    PDFs: embedded text via pdfplumber; falls back to OCR (pdf2image + pytesseract)
    for scanned/image-based PDFs that have no embedded text layer.
    Images: pytesseract (png, jpg, jpeg, tiff, tif, bmp, webp).
    """
    file_lower = file_path.lower()

    if file_lower.endswith('.pdf'):
        import pdfplumber
        text_parts = []
        with pdfplumber.open(file_path) as pdf:
            for page in pdf.pages:
                text_parts.append(page.extract_text() or '')
        embedded = '\n'.join(text_parts).strip()
        if embedded:
            return embedded

        # Scanned / image-based PDF: OCR each page via pdf2image + pytesseract.
        try:
            from pdf2image import convert_from_path
            import pytesseract
            from PIL import Image
        except ImportError:
            print("[ERROR] pdf2image or pytesseract not installed for scanned-PDF OCR.")
            return ''
        try:
            pages = convert_from_path(file_path)
            ocr_parts = []
            for page in pages:
                ocr_parts.append(pytesseract.image_to_string(page) or '')
            return '\n'.join(ocr_parts)
        except Exception as e:
            print(f"[ERROR] Scanned-PDF OCR failed (is Tesseract/Poppler installed?): {e}")
            return ''

    elif file_lower.endswith(('.png', '.jpg', '.jpeg', '.tiff', '.tif', '.bmp', '.webp')):
        import pytesseract
        from PIL import Image
        return pytesseract.image_to_string(Image.open(file_path))

    else:
        print("[ERROR] Unsupported file format.")
        return ''

def build_prompt(document_text: str) -> str:
    """Build the extraction prompt with the Pydantic schema embedded."""
    prompt = (
        "You are an expert procurement assistant reading a PhilGEPS / Bid Notice document.\n"
        "Extract BOTH the general procurement details (metadata) and ALL line items from the detailed itemized list.\n\n"
        "Return ONLY valid JSON matching this schema:\n"
        f"{json.dumps(ProcurementData.model_json_schema(), indent=2)}\n\n"
        "CRITICAL RULES:\n"
        "1. Extract quantity ONLY from the designated 'Quantity' column. Convert comma numbers like '27,000' into plain integers (27000).\n"
        "2. Ensure the ABC (Approved Budget) is a clean float number without currency symbols.\n"
        "3. For each item, distinguish a per-unit price from that item's extended line total. If a per-unit price is shown, use it and mark price_type as 'unit'. If only that item's line total is shown, use it as price and mark price_type as 'line_total'. If neither is shown, use null and mark price_type as 'missing'; never substitute the procurement-wide ABC.\n"
        "4. Do not include address lines or venue details in the item descriptions.\n"
        "5. IMPORTANT: Parse EVERY line in the detailed numbered item list (e.g. 'LIST OF MEDICINE SUPPLIES: 1. AMOXICILLIN ... 100 boxes'). Do NOT just extract the single summary row from the bottom 'All Items' table — that table usually contains one generic total row and misses every individual medicine. Return every numbered item as a separate entry in the items array.\n"
        "6. For each item: item_name = the medicine/product name, quantity = the numeric quantity, unit = the UOM (e.g. 'box', 'bottles', 'pcs', 'Lot'), description = any extra details, price = unit price if shown else line total else null.\n"
        f"\n\nDOCUMENT TEXT:\n{document_text}"
    )
    return prompt

def parse_with_freellmapi(file_path: str) -> dict:
    """Parse using FreeLLMAPI local OpenAI-compatible endpoint."""
    from openai import OpenAI

    client = OpenAI(
        base_url=os.environ.get('FREE_LLM_API_URL', 'http://localhost:3001/v1'),
        api_key=os.environ.get('FREE_LLM_API_KEY', ''),
    )

    document_text = extract_text_from_file(file_path)
    if not document_text.strip():
        print("[ERROR] No text extracted from document.")
        return {}

    prompt = build_prompt(document_text)
    max_retries = 3
    delay = 2

    for attempt in range(max_retries):
        try:
            response = client.chat.completions.create(
                model=os.environ.get('FREE_LLM_MODEL', 'auto'),
                messages=[
                    {"role": "system", "content": "You extract procurement data and return strict JSON only."},
                    {"role": "user", "content": prompt},
                ],
                response_format={"type": "json_object"},
                temperature=0.0,
            )

            parsed_data = json.loads(response.choices[0].message.content)
            parsed_data['items'] = normalize_item_prices(parsed_data.get('items', []))
            return parsed_data

        except Exception as e:
            print(f"[WARNING] FreeLLMAPI attempt {attempt + 1} failed: {e}")
            if attempt < max_retries - 1:
                time.sleep(delay)
                delay *= 2
            else:
                print("[ERROR] FreeLLMAPI max retries reached.")
                return {}

def parse_with_google_genai(file_path: str) -> dict:
    """Parse using Google GenAI (fallback for production/Vercel)."""
    from google import genai
    from google.genai import types

    client = genai.Client()

    file_lower = file_path.lower()
    if file_lower.endswith('.pdf'):
        mime_type = 'application/pdf'
    elif file_lower.endswith('.png'):
        mime_type = 'image/png'
    elif file_lower.endswith(('.jpg', '.jpeg')):
        mime_type = 'image/jpeg'
    else:
        print("[ERROR] Unsupported file format.")
        return {}

    with open(file_path, 'rb') as f:
        file_data = f.read()

    prompt = build_prompt(extract_text_from_file(file_path))

    max_retries = 3
    delay = 2

    for attempt in range(max_retries):
        try:
            response = client.models.generate_content(
                model='gemini-2.5-flash',
                contents=[
                    types.Part.from_bytes(data=file_data, mime_type=mime_type),
                    prompt
                ],
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=ProcurementData,
                    temperature=0.0
                )
            )

            parsed_data = json.loads(response.text)
            parsed_data['items'] = normalize_item_prices(parsed_data.get('items', []))
            return parsed_data

        except Exception as e:
            print(f"[WARNING] Google GenAI attempt {attempt + 1} failed: {e}")
            if attempt < max_retries - 1:
                time.sleep(delay)
                delay *= 2
            else:
                print("[ERROR] Google GenAI max retries reached.")
                return {}

def parse_bid_document(file_path: str) -> dict:
    """Parse a bid document using FreeLLMAPI first, then Google GenAI, then regex fallback."""
    free_llm_url = os.environ.get('FREE_LLM_API_URL', '')
    free_llm_key = os.environ.get('FREE_LLM_API_KEY', '')

    if free_llm_url and free_llm_key:
        result = parse_with_freellmapi(file_path)
        if result:
            return result
        print("[INFO] FreeLLMAPI failed, falling back to Google GenAI.")

    result = parse_with_google_genai(file_path)
    if result:
        return result
    print("[INFO] Google GenAI failed, falling back to regex-only parsing.")

    # Final fallback: regex rules (no API, no limits)
    from app.utils.regex_parser import parse_bid_document_regex
    result = parse_bid_document_regex(file_path)
    if result:
        print("[INFO] Regex parsing succeeded.")
        return result

    return {}
