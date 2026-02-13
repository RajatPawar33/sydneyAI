from datetime import datetime
from typing import Any, Dict

from fastapi import APIRouter, Header, HTTPException, Request
from services.database import db_service
from services.email import mailgun_client

router = APIRouter(prefix="/webhooks", tags=["webhooks"])

# only the events we care about for campaign reporting
TRACKED_EVENTS = {
    "delivered",
    "opened",
    "clicked",
    "failed",
    "unsubscribed",
    "complained",
}


@router.post("/mailgun")
async def mailgun_webhook(
    request: Request,
    content_type: str = Header(default=""),
):
    # mailgun posts form data, not json
    form = await request.form()
    payload = dict(form)

    # --- verify signature ---
    signature_data = payload.get("signature", {})
    if isinstance(signature_data, str):
        # flat form: signature fields are top-level
        ts = payload.get("timestamp", "")
        token = payload.get("token", "")
        sig = payload.get("signature", "")
    else:
        ts = signature_data.get("timestamp", "")
        token = signature_data.get("token", "")
        sig = signature_data.get("signature", "")

    if not mailgun_client.verify_webhook(ts, token, sig):
        raise HTTPException(status_code=403, detail="invalid webhook signature")

    # --- extract event data ---
    event_data = payload.get("event-data", payload)
    event_type = event_data.get("event", payload.get("event", ""))

    if event_type not in TRACKED_EVENTS:
        # acknowledge but skip irrelevant events
        return {"status": "ignored"}

    await _process_event(event_type, event_data)

    return {"status": "ok"}


async def _process_event(event_type: str, data: Dict[str, Any]):
    # extract common fields
    recipient = data.get("recipient", "")
    message_id = (
        (data.get("message", {}) or {}).get("headers", {}).get("message-id", "")
    )
    timestamp = datetime.fromtimestamp(float(data.get("timestamp", 0)))
    tags = data.get("tags", [])

    # campaign_id is stored as the first tag on every send
    campaign_id = tags[0] if tags else None

    event_doc = {
        "event_type": event_type,
        "recipient": recipient,
        "message_id": message_id,
        "campaign_id": campaign_id,
        "timestamp": timestamp,
        "raw": data,
    }

    # persist event
    await db_service.db.email_events.insert_one(event_doc)

    # update campaign-level counters in one atomic op
    if campaign_id:
        increment_field = _event_to_counter(event_type)
        if increment_field:
            await db_service.db.campaigns.update_one(
                {"id": campaign_id},
                {
                    "$inc": {f"stats.{increment_field}": 1},
                    "$set": {"stats.updated_at": datetime.now()},
                },
            )


def _event_to_counter(event_type: str) -> str | None:
    mapping = {
        "delivered": "delivered",
        "opened": "opens",
        "clicked": "clicks",
        "failed": "bounces",
        "unsubscribed": "unsubscribes",
        "complained": "spam_reports",
    }
    return mapping.get(event_type)
