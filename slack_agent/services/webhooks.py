from datetime import datetime
from typing import Any, Dict

from fastapi import APIRouter, Header, HTTPException, Request, Form, Response

from slack_agent.services.database import db_service
from slack_agent.services.email import mailgun_client
from fastapi import APIRouter, Query
from fastapi.responses import RedirectResponse
from slack_agent.services.database import db_service
from datetime import datetime
from typing import List
import logging
from datetime import datetime
from typing import Any, Dict, List
import logging
from fastapi.responses import RedirectResponse
from twilio.request_validator import RequestValidator
from slack_agent.config.settings import settings

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

twilio_validator = RequestValidator(settings.twilio_auth_token)

logger = logging.getLogger(__name__)

@router.get("/track/click")
async def track_campaign_click(
    email: str = Query(...),
    name: str = Query("Customer"),
    campaign_id: str = Query(...),
    product_title: str = Query(...),
    product_type: str = Query(""),
    product_id: str = Query(...),
    product_tags: List[str] = Query([])
    
):
    try:
        # 1. Process and structure the incoming lead payload
        lead_payload = {
            "name": name,
            "email": email,
            "status": "interested",
            "campaign_id": campaign_id,
            "source": "email_click",
            "last_action_at": datetime.utcnow(),
            "product_type": product_type,
            "tags": product_tags,
            "interest_metadata": {
                "product_title": product_title,
                "product_type": product_type,
                "product_tags": product_tags
            }
        }
        
        # 2. Record or update user preferences in your MongoDB leads collection
        await db_service.db.leads.update_one(
            {"email": email},
            {
                "$set": lead_payload, 
                "$setOnInsert": {"created_at": datetime.utcnow()} 
            },
            upsert=True
        )
        print(f"Captured email click warm lead: {email}")
    except Exception as e:
        print(f"Error logging click lead: {str(e)}")

    # 3. Construct the clean Vercel redirect deep-link URL
    STORE_BASE_URL = "https://sydney-store-eight.vercel.app"
    clean_redirect_url = f"{STORE_BASE_URL}/#product/{product_id}"
    
    print(f"Redirecting safely to clean destination URL: {clean_redirect_url}")
    return RedirectResponse(url=clean_redirect_url)    
   
    

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

@router.post("/whatsapp")
async def whatsapp_webhook(
    request: Request,
    From: str = Form(...),
    To: str = Form(...),
    Body: str = Form(...),
    MessageSid: str = Form(...)
):
    
    try:
        # Extract phone number as the unique identifier (e.g., "+14155552671")
        user_id = From.replace("whatsapp:", "")
        
        # Pull the global SlackHandler instance shared via app state
        slack_handler = getattr(request.app.state, "slack_handler", None)
        if not slack_handler:
            twiml_error = (
                '<?xml version="1.0" encoding="UTF-8"?>'
                "<Response><Message>Agent service is temporarily offline.</Message></Response>"
            )
            return Response(content=twiml_error, media_type="application/xml")

        # Build execution context metadata matching what SlackHandler expects
        user_info = {
            "id": user_id,
            "name": f"WhatsApp User ({user_id})",
            "username": user_id
        }
        channel_info = {
            "id": "whatsapp-channel",
            "name": "whatsapp"
        }

        # 1. Fetch conversation history from MongoDB using the phone number as user_id
        conv_history = await db_service.get_conversation_history(user_id, limit=5)

        # 2. Forward execution directly into the semantic router and tool dispatcher
        response_text = await slack_handler._process_command(
            Body, user_info, channel_info, conv_history
        )

        # 3. Clean Slack formatting wrappers out of the message context for WhatsApp readability
        # Strip out Slack's explicit hyperlink markdown (<http://url|label> or <mailto:email|label>)
        import re
        response_text = re.sub(r"<(?:mailto:)?([^|>]+)(?:\|[^>]+)?>", r"\1", response_text)

        # 4. Persist transaction history to MongoDB logs
        await db_service.save_conversation(
            user_id=user_id,
            channel_id="whatsapp-channel",
            message=Body,
            response=response_text
        )

        # 5. Build and return TwiML XML response payload
        twiml_response = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            f"<Response><Message>{response_text}</Message></Response>"
        )
        return Response(content=twiml_response, media_type="application/xml")

    except Exception as e:
        logger.error(f"Error handling WhatsApp message webhook: {str(e)}")
        twiml_fallback = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            "<Response><Message>An error occurred processing your request.</Message></Response>"
        )
        return Response(content=twiml_fallback, media_type="application/xml")

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


from slack_agent.models.schemas import WebsiteQuizLead  # Import the new schema

@router.post("/api/leads/website")
async def track_website_personalization(payload: WebsiteQuizLead):
    """
    Handles inbound leads from your website's style quiz form.
    Validates and stores user context into MongoDB for future marketing triggers.
    """
    try:
        # Pydantic automatically validates and safe-parses the properties
        email = payload.email
        name = payload.name
        chosen_tags = payload.tags
        chosen_type = payload.product_type

        lead_payload = {
            "name": name,
            "email": email,
            "status": "interested",
            "source": "website_personalization",
            "last_action_at": datetime.utcnow(),
            # These matching variables align with campaign segmentations
            "product_type": chosen_type,
            "tags": chosen_tags,
            "interest_metadata": {
                "product_type": chosen_type,
                "product_tags": chosen_tags
            }
        }
        
        # Upsert operation ensures that if an email takes the quiz multiple times,
        # their profile state and style preferences are refreshed dynamically.
        await db_service.db.leads.update_one(
            {"email": email},
            {
                "$set": lead_payload, 
                "$setOnInsert": {"created_at": datetime.utcnow()}
            },
            upsert=True
        )
        return {"status": "success", "message": "Website quiz lead captured and structured successfully."}
    except Exception as e:
        logger.error(f"Error saving quiz lead: {str(e)}")
        return {"status": "error", "message": "Internal storage failure"}