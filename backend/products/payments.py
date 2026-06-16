import logging
import uuid

import httpx
from django.conf import settings

logger = logging.getLogger(__name__)


def _mock_payment(order, amount):
    return {
        "external_id": f"mock-{uuid.uuid4()}",
        "status": "succeeded",
        "confirmation_url": "",
        "mock": True,
    }


def create_payment(order, return_url):
    amount = float(order.total)
    shop_id = getattr(settings, "YOOKASSA_SHOP_ID", "")
    secret_key = getattr(settings, "YOOKASSA_SECRET_KEY", "")

    if not shop_id or not secret_key:
        logger.info("YooKassa keys not configured, using mock payment for order %s", order.id)
        return _mock_payment(order, amount)

    payload = {
        "amount": {"value": f"{amount:.2f}", "currency": "RUB"},
        "confirmation": {"type": "redirect", "return_url": return_url},
        "capture": True,
        "description": f"Заказ #{order.id} — Store with AI",
        "metadata": {"order_id": str(order.id)},
    }

    try:
        response = httpx.post(
            "https://api.yookassa.ru/v3/payments",
            json=payload,
            auth=(shop_id, secret_key),
            headers={"Idempotence-Key": str(uuid.uuid4()), "Content-Type": "application/json"},
            timeout=20.0,
        )
        response.raise_for_status()
        data = response.json()
        return {
            "external_id": data.get("id", ""),
            "status": data.get("status", "pending"),
            "confirmation_url": data.get("confirmation", {}).get("confirmation_url", ""),
            "mock": False,
        }
    except Exception:
        logger.exception("YooKassa payment creation failed for order %s", order.id)
        raise


def check_payment_status(external_id):
    shop_id = getattr(settings, "YOOKASSA_SHOP_ID", "")
    secret_key = getattr(settings, "YOOKASSA_SECRET_KEY", "")

    if external_id.startswith("mock-"):
        return "succeeded"

    if not shop_id or not secret_key:
        return "pending"

    try:
        response = httpx.get(
            f"https://api.yookassa.ru/v3/payments/{external_id}",
            auth=(shop_id, secret_key),
            timeout=15.0,
        )
        response.raise_for_status()
        return response.json().get("status", "pending")
    except Exception:
        logger.exception("Failed to check payment %s", external_id)
        return "pending"
