import os
from typing import Optional

import requests


def pipeline_upload(file_path: str, callback_id: Optional[str] = None) -> Optional[dict]:
    base_url = (os.environ.get("PROCUREMENT_PIPELINE_URL") or "").rstrip("/")
    if not base_url:
        return None

    headers = {}
    token = (os.environ.get("PROCUREMENT_PIPELINE_TOKEN") or "").strip()
    if token:
        headers["Authorization"] = f"Bearer {token}"

    try:
        with open(file_path, "rb") as pdf_file:
            response = requests.post(
                f"{base_url}/v1/extract/upload",
                headers=headers,
                data={"callbackId": callback_id or ""},
                files={"file": (os.path.basename(file_path), pdf_file, "application/pdf")},
                timeout=300,
            )
    except requests.RequestException as exc:
        raise RuntimeError(f"Could not reach procurement pipeline: {exc}") from exc

    if not response.ok:
        raise RuntimeError(
            f"Procurement pipeline returned HTTP {response.status_code}: "
            f"{response.text[:300]}"
        )

    return response.json()


def convert_pipeline_payload(webhook_response: dict) -> dict:
    result = webhook_response.get("result") or {}
    payload = result.get("payload") or {}
    medicines = payload.get("medicines") or []

    items = []
    for medicine in medicines:
        quantity = medicine.get("quantity")
        unit_price = medicine.get("unitPrice")
        description = medicine.get("dosageOrForm") or ""
        package_value = medicine.get("packageSizeValue")
        package_unit = medicine.get("packageSizeUnit")
        if package_value is not None or package_unit:
            package = " ".join(
                str(value)
                for value in (package_value, package_unit)
                if value is not None
            )
            description = " ".join(part for part in (description, f"Pack: {package}") if part)

        items.append(
            {
                "item_name": medicine.get("name") or "Unnamed Item",
                "quantity": quantity if isinstance(quantity, int) else 1,
                "unit": medicine.get("unit") or "pcs",
                "description": description,
                "price": unit_price if isinstance(unit_price, (int, float)) else None,
                "price_type": "unit" if unit_price is not None else "missing",
            }
        )

    abc_amount = payload.get("abcAmount")
    metadata = {
        "procurement_title": "Scanned Bid Notice",
        "abc": abc_amount if isinstance(abc_amount, (int, float)) else 0.0,
        "pre_bid_conference_date": payload.get("bidDate") or "N/A",
        "place_of_bidding": payload.get("place") or "N/A",
        "municipality": "N/A",
        "agency_requested": "N/A",
    }

    return {
        "metadata": metadata,
        "items": items,
        "_pipeline": {
            "publish_status": result.get("publish_status"),
            "quality_flags": result.get("quality_flags") or [],
            "training_candidates": result.get("training_candidates") or [],
        },
    }
