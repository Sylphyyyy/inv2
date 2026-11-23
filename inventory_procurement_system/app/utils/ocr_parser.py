import os
import json
import time
from google import genai
from google.genai import types
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

def parse_bid_document(file_path):
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

    # The prompt can now be much shorter because Pydantic handles the formatting!
    prompt = (
        "You are an expert procurement assistant reading a PhilGEPS / Bid Notice document.\n"
        "Extract BOTH the general procurement details (metadata) and ALL line items from the detailed itemized list.\n\n"
        "CRITICAL RULES:\n"
        "1. Extract quantity ONLY from the designated 'Quantity' column. Convert comma numbers like '27,000' into plain integers (27000).\n"
        "2. Ensure the ABC (Approved Budget) is a clean float number without currency symbols.\n"
        "3. For each item, distinguish a per-unit price from that item's extended line total. If a per-unit price is shown, use it and mark price_type as 'unit'. If only that item's line total is shown, use it as price and mark price_type as 'line_total'. If neither is shown, use null and mark price_type as 'missing'; never substitute the procurement-wide ABC.\n"
        "4. Do not include address lines or venue details in the item descriptions.\n"
        "5. IMPORTANT: Parse EVERY line in the detailed numbered item list (e.g. 'LIST OF MEDICINE SUPPLIES: 1. AMOXICILLIN ... 100 boxes'). Do NOT just extract the single summary row from the bottom 'All Items' table — that table usually contains one generic total row and misses every individual medicine. Return every numbered item as a separate entry in the items array.\n"
        "6. For each item: item_name = the medicine/product name, quantity = the numeric quantity, unit = the UOM (e.g. 'box', 'bottles', 'pcs', 'Lot'), description = any extra details, price = unit price if shown else line total else null.\n"
    )

    max_retries = 3
    delay = 2

    for attempt in range(max_retries):
        try:
            response = client.models.generate_content(
                model='gemini-3.5-flash-lite',
                contents=[
                    types.Part.from_bytes(data=file_data, mime_type=mime_type),
                    prompt
                ],
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    # Pass the Pydantic model directly to force perfect JSON generation
                    response_schema=ProcurementData,
                    temperature=0.0
                )
            )
            
            # Normalize item line totals to unit prices; do not estimate from the procurement ABC.
            parsed_data = json.loads(response.text)
            parsed_data['items'] = normalize_item_prices(parsed_data.get('items', []))
            return parsed_data

        except Exception as e:
            print(f"[WARNING] Attempt {attempt + 1} failed due to traffic/error: {e}")
            if attempt < max_retries - 1:
                time.sleep(delay)
                delay *= 2  # Double the wait time for the next retry
            else:
                print("[ERROR] Max retries reached. Gemini extraction failed.")
                return {}
