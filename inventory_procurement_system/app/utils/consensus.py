from app.utils.ocr_parser import parse_with_freellmapi, parse_with_google_genai
from app.utils.regex_parser import parse_bid_document_regex


def parse_with_consensus(file_path: str) -> dict:
    """Run LLM + regex parsers and cross-check results for mismatches."""
    llm = parse_with_freellmapi(file_path) or parse_with_google_genai(file_path) or {}
    regex = parse_bid_document_regex(file_path) or {}

    mismatches = []
    if llm.get('metadata', {}).get('abc') != regex.get('metadata', {}).get('abc'):
        mismatches.append('abc')
    if len(llm.get('items', [])) != len(regex.get('items', [])):
        mismatches.append('item_count')

    return {
        'llm': llm,
        'regex': regex,
        'mismatches': mismatches,
        'needs_review': len(mismatches) > 0,
    }
