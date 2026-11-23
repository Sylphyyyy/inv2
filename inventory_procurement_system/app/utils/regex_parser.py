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


_UNITS = (
    r'box|boxes|pcs|bottle|bottles|lot|lots|roll|rolls|pack|packs|'
    r'piece|pieces|unit|units|set|sets|bundle|bundles|ream|reams|'
    r'jar|jars|tube|tubes|can|cans|ampoule|ampoules|vial|vials|'
    r'sachet|sachets|tab|tabs|bottle|bottles'
)


def extract_metadata(text: str) -> Dict[str, Any]:
    """Extract procurement metadata using regex patterns."""
    metadata = {
        'procurement_title': 'N/A',
        'reference_number': 'N/A',
        'procuring_entity': 'N/A',
        'solicitation_number': 'N/A',
        'trade_agreement': 'N/A',
        'procurement_mode': 'N/A',
        'classification': 'N/A',
        'category': 'N/A',
        'abc': None,
        'delivery_period': 'N/A',
        'client_agency': 'N/A',
        'contact_person': 'N/A',
        'date_published': 'N/A',
        'last_updated': 'N/A',
        'closing_date': 'N/A',
        'status': 'N/A',
        'associated_components': 'N/A',
        'bid_supplements': 'N/A',
        'document_request_list': 'N/A',
        'pre_bid_conference_date': 'N/A',
        'place_of_bidding': 'N/A',
        'municipality': 'N/A',
        'agency_requested': 'N/A',
    }

    def _field(patterns: str, flags=re.IGNORECASE) -> Optional[str]:
        if isinstance(patterns, str):
            patterns = [patterns]
        for pat in patterns:
            m = re.search(pat, text, flags)
            if m:
                return m.group(1).strip()
        return None

    # Title: prefer explicit "Title:" label; avoid matching the bare header
    title_patterns = [
        r'Project Title[:\s]+(.+?)(?=\n|$)',
        r'Name of Project[:\s]+(.+?)(?=\n|$)',
        r'Title[:\s]+(.+?)(?=\n|$)',
        r'Invitation to Bid:\s+(.+?)(?=\n|$)',
        r'Procurement of[:\s]+(.+?)(?=\n|$)',
    ]
    metadata['procurement_title'] = _field(title_patterns) or 'N/A'

    # Reference / solicitation numbers
    metadata['reference_number'] = _field([
        r'Reference Number[:\s]+([\w\s\-/]+)',
        r'RFQ Number[:\s]+([\w\s\-/]+)',
        r'ITB Number[:\s]+([\w\s\-/]+)',
    ]) or 'N/A'
    metadata['solicitation_number'] = _field([
        r'Solicitation Number[:\s]+([\w\s\-/]+)',
        r'PR Number[:\s]+([\w\s\-/]+)',
    ]) or 'N/A'

    # Procuring entity / agency
    metadata['procuring_entity'] = _field([
        r'Procuring Entity[:\s]+(.+?)(?=\n|$)',
        r'Government Agency[:\s]+(.+?)(?=\n|$)',
        r'Agency[:\s]+(.+?)(?=\n|$)',
    ]) or 'N/A'
    metadata['agency_requested'] = metadata['procuring_entity'] if metadata['procuring_entity'] != 'N/A' else 'N/A'

    # Classification / category / mode / trade agreement
    metadata['classification'] = _field([r'Classification[:\s]+(.+?)(?=\n|$)']) or 'N/A'
    metadata['category'] = _field([r'Category[:\s]+(.+?)(?=\n|$)']) or 'N/A'
    metadata['procurement_mode'] = _field([r'Procurement Mode[:\s]+(.+?)(?=\n|$)']) or 'N/A'
    metadata['trade_agreement'] = _field([r'Trade Agreement[:\s]+(.+?)(?=\n|$)']) or 'N/A'

    # ABC: Approved Budget for the Contract (e.g. "₱ 1,257,880.00")
    abc_patterns = [
        r'Approved Budget for the Contract[:\s]+₱?\s*([\d,]+\.?\d*)',
        r'ABC[:\s]+₱?\s*([\d,]+\.?\d*)',
        r'Total ABC[:\s]+₱?\s*([\d,]+\.?\d*)',
        r'Approved Budget[:\s]+₱?\s*([\d,]+\.?\d*)',
    ]
    abc_val = _field(abc_patterns)
    metadata['abc'] = clean_currency(abc_val) if abc_val else None

    # Delivery period
    metadata['delivery_period'] = _field([r'Delivery Period[:\s]+(.+?)(?=\n|$)']) or 'N/A'
    metadata['client_agency'] = _field([r'Client Agency[:\s]+(.+?)(?=\n|$)']) or 'N/A'

    # Contact person (multiline block up to the next field)
    contact = _field([r'Contact Person:\s*(.+?)(?=\n\s*Date Published)'], re.IGNORECASE | re.DOTALL)
    metadata['contact_person'] = re.sub(r'\s+', ' ', contact).strip() if contact else 'N/A'

    # Dates: DD/MM/YYYY and DD/MM/YYYY HH:MM AM/PM
    date_only = r'\d{1,2}/\d{1,2}/\d{4}'
    date_time = r'\d{1,2}/\d{1,2}/\d{4}\s+\d{1,2}:\d{2}\s*(?:AM|PM)?'
    metadata['date_published'] = _field([rf'Date Published[:\s]+({date_only})']) or 'N/A'
    metadata['last_updated'] = _field([rf'Last Updated[/\s]*Time[:\s]+({date_time})']) or 'N/A'
    metadata['closing_date'] = _field([rf'Closing Date[/\s]*Time[:\s]+({date_time})']) or 'N/A'

    # Status and component/supplement counts
    metadata['status'] = _field([r'Status[:\s]+(.+?)(?=\n|$)']) or 'N/A'
    metadata['associated_components'] = _field([r'Associated Components[:\s]*(\d+)']) or 'N/A'
    metadata['bid_supplements'] = _field([r'Bid Supplements[:\s]*(\d+)']) or 'N/A'
    metadata['document_request_list'] = _field([r'Document Request List[:\s]*(\d+)']) or 'N/A'

    # Pre-bid conference
    prebid_patterns = [
        r'Pre-bid Conference[:\s]+(.+?)(?=\n|$)',
        r'Pre-bid[:\s]+(.+?)(?=\n|$)',
        rf'({date_time})',
    ]
    metadata['pre_bid_conference_date'] = _field(prebid_patterns) or 'N/A'

    # Place / venue / municipality
    place_patterns = [
        r'Place of Bidding[:\s]+(.+?)(?=\n|$)',
        r'Venue[:\s]+(.+?)(?=\n|$)',
    ]
    metadata['place_of_bidding'] = _field(place_patterns) or 'N/A'
    mun_patterns = [
        r'Municipality[:\s]+(.+?)(?=\n|$)',
        r'City of\s+(.+?)(?=\n|$)',
        r'City\s*[:\-]\s*(.+?)(?=\n|$)',
    ]
    metadata['municipality'] = _field(mun_patterns) or 'N/A'

    return metadata


def extract_items(text: str) -> List[Dict[str, Any]]:
    """Extract line items from numbered lists in bid documents.

    Handles formats like:
      1. AMOXICILLIN 500mg 100 'box' .... 100 boxes                (no price)
      1. AMOXICILLIN 500mg 100 'box' .... 100 boxes .... ₱50.00   (with price)
      23. METFORMIN HCl 500 MG 100's tab .... 100 boxes .... ₱100 boxes

    Each line that starts with "N." is treated as one item. The real
    quantity/unit is the LAST quantity+unit pair on the line (earlier
    "100 'box'"-style tokens are pack-size description kept in the name).
    Price is optional since it may be cut off at the page edge.
    """
    items = []

    for line in text.splitlines():
        head = re.match(r'^\s*(\d+)\.\s+(.+)$', line, re.IGNORECASE)
        if not head:
            continue
        item_num = head.group(1)
        rest = head.group(2)

        # All quantity+unit pairs on the line; the LAST one is the real UOM.
        pairs = list(re.finditer(r'(\d+)\s+(' + _UNITS + r')\b', rest, re.IGNORECASE))
        if not pairs:
            continue
        last = pairs[-1]
        quantity = clean_int(last.group(1))
        unit = last.group(2).strip()

        # Item name = everything before the last quantity+unit pair.
        name_part = rest[:last.start()].strip()
        name_part = re.sub(r'\.+\s*$', '', name_part).strip()

        # Price: a currency-looking number after the last unit pair.
        price = None
        tail = rest[last.end():]
        pm = re.search(r'₱?\s*([\d,]+\.?\d*)', tail)
        if pm:
            price = clean_currency(pm.group(1))

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
