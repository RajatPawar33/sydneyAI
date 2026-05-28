from datetime import datetime
from typing import Any, Dict

from fastapi import APIRouter, Header, HTTPException, Request

from slack_agent.services.database import db_service
from slack_agent.services.email import mailgun_client

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
from fastapi import APIRouter, Query
from fastapi.responses import RedirectResponse
from slack_agent.services.database import db_service
from datetime import datetime
from typing import List
import logging

logger = logging.getLogger(__name__)

@router.get("/track/click")
async def track_campaign_click(
    email: str = Query(...),
    name: str = Query("Customer"),
    campaign_id: str = Query(...),
    product_title: str = Query(...),
    product_type: str = Query(""),
    product_tags: List[str] = Query([]),
    redirect_url: str = Query(...)
):
    """
    Handles outbound tracking clicks forwarded by SendGrid/ngrok.
    Logs the warm lead and redirects to the temporary destination (Wikipedia).
    """
    try:
        # lead_payload = {
        #     "name": name,
        #     "email": email,
        #     "status": "interested",
        #     "campaign_id": campaign_id,
        #     "source": "email_click",
        #     "last_action_at": datetime.utcnow(),
        #     "interest_metadata": {
        #         "product_title": product_title,
        #         "product_type": product_type,
        #         "product_tags": product_tags
        #     }
        # }
        # await db_service.db.leads.update_one(
        #     {"email": email},
        #     {"$set": lead_payload, "$setOnInsert": {"created_at": datetime.utcnow()}},
        #     upsert=True
        # )
        print(f"Captured email click warm lead: {email}")
    except Exception as e:
        print(f"Error logging click lead: {str(e)}")

    return RedirectResponse(url=redirect_url)


@router.post("/api/leads/website")
async def track_website_personalization(payload: dict):
    """
    Handles inbound leads from your new website's pop-up form.
    Receives user info and their selected personalization preferences.
    """
    try:
        email = payload.get("email")
        name = payload.get("name", "Website Visitor")
        searched_tags = payload.get("tags", [])
        searched_type = payload.get("product_type", "")

        lead_payload = {
            "name": name,
            "email": email,
            "status": "interested",
            "source": "website_personalization",
            "last_action_at": datetime.utcnow(),
            "interest_metadata": {
                "product_type": searched_type,
                "product_tags": searched_tags
            }
        }
        
        await db_service.db.leads.update_one(
            {"email": email},
            {
                "$set": lead_payload, 
                "$setOnInsert": {"created_at": datetime.utcnow()}
            },
            upsert=True
        )
        return {"status": "success", "message": "Website lead captured automatically"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

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

@router.post("/sendgrid")
async def sendgrid_webhook(request: Request):
    data = await request.json()

    for event in data:
        event_type = event.get("event", "")

        if event_type not in TRACKED_EVENTS:
            continue

        await _process_event(event_type, event)

    return {"status": "ok"}

async def _process_event(event_type: str, data: Dict[str, Any]):
    # 1. Extract recipient: SendGrid uses the key "email"
    recipient = data.get("email", data.get("recipient", "unknown"))

    # 2. Extract Message ID: SendGrid uses "sg_message_id"
    message_id = data.get("sg_message_id", "unknown")

    # 3. Handle Timestamp
    timestamp = datetime.fromtimestamp(float(data.get("timestamp", 0)))

    # 4. Extract campaign_id from Custom Args
    
    campaign_id = None
    for key, value in data.items():
        if key.startswith("tag_"):
            campaign_id = value
            break

    # If not found via prefix, check for a direct "campaign_id" or "tags" fallback
    if not campaign_id:
        tags = data.get("tags", [])
        campaign_id = tags[0] if isinstance(tags, list) and tags else data.get("campaign_id")

    event_doc = {
        "event_type": event_type,
        "recipient": recipient,
        "message_id": message_id,
        "campaign_id": campaign_id,
        "timestamp": timestamp,
        "raw": data, # Keeps the full SendGrid payload for debugging
    }

    # Persist event to the audit log
    await db_service.db.email_events.insert_one(event_doc)

    # 5. Update campaign-level counters in the 'campaigns' collection
    if campaign_id:
        increment_field = _event_to_counter(event_type)
        if increment_field:
            # Matches the 'id' field in your campaigns collection screenshot
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
