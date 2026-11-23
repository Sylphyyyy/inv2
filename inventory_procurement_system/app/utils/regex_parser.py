import re
from typing import List, Optional, Dict, Any


def clean_currency(value: str) -> Optional[float]:
    """Remove currency symbols, commas, spaces and convert to float."""
    if not value:
        return None
    cleaned = re.sub(r'[₱,\s]', '', value)
    try:
        return float(cleaned)
    except ValueError:
        return None


def clean_int(value: str) -> Optional[int]:
    """Remove commas and spaces and convert to int."""
    if not value:
        return None
    cleaned = re.sub(r'[,\s]', '', value)
    try:
        return int(cleaned)
    except ValueError:
        return None


def extract_metadata(text: str) -> Dict[str, Any]:
    """Extract procurement metadata using regex patterns."""
    metadata = {
        'procurement_title': 'N/A',
        'abc': None,
        'pre_bid_conference_date': 'N/A',
        'place_of_bidding': 'N/A',
        'municipality': 'N/A',
        'agency_requested': 'N/A',
    }

    # Title: look for common PhilGEPS title patterns
    title_patterns = [
        r'Project Title[:\s]+(.+?)(?=\n|$)',
        r'Name of Project[:\s]+(.+?)(?=\n|$)',
        r'Invitation to Bid[:\s]+(.+?)(?=\n|$)',
        r'Procurement of[:\s]+(.+?)(?=\n|$)',
        r'Title[:\s]+(.+?)(?=\n|$)',
    ]
    for pattern in title_patterns:
        m = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
        if m:
            metadata['procurement_title'] = m.group(1).strip()
            break

    # ABC: Approved Budget for the Contract
    abc_patterns = [
        r'Approved Budget for the Contract[:\s]+₱?\s*([\d,]+\.?\d*)',
        r'ABC[:\s]+₱?\s*([\d,]+\.?\d*)',
        r'Total ABC[:\s]+₱?\s*([\d,]+\.?\d*)',
        r'Approved Budget[:\s]+₱?\s*([\d,]+\.?\d*)',
    ]
    for pattern in abc_patterns:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            metadata['abc'] = clean_currency(m.group(1))
            break

    # Pre-bid conference date/time
    prebid_patterns = [
        r'Pre-bid Conference[:\s]+(.+?)(?=\n|$)',
        r'Pre-bid[:\s]+(.+?)(?=\n|$)',
        r'(\d{1,2}/\d{1,2}/\d{4}\s+\d{1,2}:\d{2}\s*(?:AM|PM)?)',
    ]
    for pattern in prebid_patterns:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            metadata['pre_bid_conference_date'] = m.group(1).strip()
            break

    # Place of bidding
    place_patterns = [
        r'Place of Bidding[:\s]+(.+?)(?=\n|$)',
        r'Venue[:\s]+(.+?)(?=\n|$)',
    ]
    for pattern in place_patterns:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            metadata['place_of_bidding'] = m.group(1).strip()
            break

    # Municipality
    mun_patterns = [
        r'Municipality[:\s]+(.+?)(?=\n|$)',
        r'City[:\s]+(.+?)(?=\n|$)',
    ]
    for pattern in mun_patterns:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            metadata['municipality'] = m.group(1).strip()
            break

    # Agency / Procuring entity
    agency_patterns = [
        r'Government Agency[:\s]+(.+?)(?=\n|$)',
        r'Procuring Entity[:\s]+(.+?)(?=\n|$)',
        r'Agency[:\s]+(.+?)(?=\n|$)',
    ]
    for pattern in agency_patterns:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            metadata['agency_requested'] = m.group(1).strip()
            break

    return metadata


def extract_items(text: str) -> List[Dict[str, Any]]:
    """Extract line items from numbered lists in bid documents.

    Matches patterns like:
      1. AMOXICILLIN 500mg 100 'box' ... 100 boxes ... ₱50.00
    """
    items = []

    # Pattern: number. name ... quantity unit ... price
    item_pattern = re.compile(
        r'^\s*(\d+)\.\s+(.+?)\s+(\d+)\s+'
        r'(box|boxes|pcs|bottles|bottle|lot|Lot|roll|rolls|pack|packs|'
        r'piece|pieces|unit|units|set|sets|bundle|bundles|ream|reams|'
        r'jar|jars|tube|tubes|can|cans|ampoule|ampoules|vial|vials|'
        r'sachet|sachets|bottle|bottles)\b'
        r'.*?₱?\s*([\d,]+\.?\d*)',
        re.IGNORECASE | re.MULTILINE,
    )

    for m in item_pattern.finditer(text):
        item_num = m.group(1)
        name_part = m.group(2).strip()
        quantity = clean_int(m.group(3))
        unit = m.group(4).strip()
        price = clean_currency(m.group(5))

        items.append({
            'item_name': name_part,
            'quantity': quantity,
            'unit': unit,
            'description': '',
            'price': price,
            'price_type': 'unit' if price is not None else 'missing',
        })

    return items


def parse_bid_document_regex(file_path: str) -> Dict[str, Any]:
    """Parse a bid document using regex rules only (no API, no limits)."""
    from app.utils.ocr_parser import extract_text_from_file

    document_text = extract_text_from_file(file_path)
    if not document_text.strip():
        return {}

    metadata = extract_metadata(document_text)
    items = extract_items(document_text)

    return {
        'metadata': metadata,
        'items': items,
    }
