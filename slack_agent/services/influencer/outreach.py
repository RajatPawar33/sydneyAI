import json
import requests
from datetime import datetime
from typing import Dict, List, Optional

from slack_agent.config.settings import settings
from slack_agent.models.schemas import (
    InfluencerCampaign,
    InfluencerProfile,
    InfluencerStatus,
    NegotiationState,
)
from slack_agent.services.database import db_service
from slack_agent.services.email import mailgun_client


class InfluencerOutreach:
    def __init__(self):
        self.base_url = settings.ollama_base_url
        self.model = settings.ollama_model

    
    async def _call_llm(self, prompt: str) -> str:
        try:
            response = requests.post(
                f"{self.base_url}/api/generate",
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "temperature": 0.7,
                        "num_predict": 800,
                    },
                },
                timeout=60,
            )
            return response.json().get("response", "")
        except Exception:
            return ""

    # --- outreach email generation ---
    async def generate_outreach_email(
        self,
        influencer: InfluencerProfile,
        campaign: InfluencerCampaign,
    ) -> Dict[str, str]:

        prompt = f"""
Write a personalized influencer outreach email.

Influencer:
- Name: {influencer.name}
- Platform: {influencer.platform}
- Niche: {", ".join(influencer.tags) if influencer.tags else campaign.target_niche}
- Followers: {influencer.followers}

Product:
- Name: {campaign.product_name}
- Description: {campaign.product_description}

Rules:
- Subject < 60 chars
- Body < 200 words
- Professional but warm
- Mention their niche
- Ask for collaboration

Return ONLY JSON:
{{"subject": "...", "body": "..."}}
"""

        try:
            text = await self._call_llm(prompt)

            cleaned = (
                text.replace("```json", "")
                .replace("```", "")
                .strip()
            )

            return json.loads(cleaned)

        except Exception:
            return {
                "subject": f"Collaboration with {campaign.product_name}",
                "body": f"Hi {influencer.name}, we'd love to collaborate with you!",
            }
    async def send_outreach(
        self,
        influencer: InfluencerProfile,
        campaign: InfluencerCampaign,
        attachment_paths: Optional[List[str]] = None,
    ) -> bool:
        """
        Sends an outreach email using the SendGrid-backed email service.
        """
        # 1. Validation: Ensure influencer has an email address
        if not influencer.email:
            return False

        # 2. Content Generation: Use LLM to generate subject and body
        email_content = await self.generate_outreach_email(influencer, campaign)

        # 3. Attachment Setup: Check for provided paths or campaign defaults
        attach_paths = attachment_paths or campaign.product_attachment_paths

        # 4. Email Dispatch: Use the client (now SendGrid internally)
        if attach_paths:
            # SendGrid logic encodes this file as Base64 internally
            result = await mailgun_client.send_with_attachment(
                to=influencer.email,
                subject=email_content["subject"],
                text=email_content["body"],
                attachment_path=attach_paths[0],
                tags=[campaign.id, "influencer_outreach"],
            )
        else:
            # Standard send using SendGrid's Mail object
            result = await mailgun_client.send(
                to=influencer.email,
                subject=email_content["subject"],
                text=email_content["body"],
                tags=[campaign.id, "influencer_outreach"],
            )

        # 5. Database Update: If successful, update the influencer status in MongoDB
        if result.get("success"):
            await db_service.db.influencers.update_one(
                {"id": influencer.id},
                {
                    "$set": {
                        "status": InfluencerStatus.CONTACTED,
                        "last_contacted_at": datetime.now(),
                    }
                },
            )
            return True

        return False
    

    # --- negotiation ---
    async def handle_reply(
        self,
        influencer_id: str,
        campaign_id: str,
        their_message: str,
    ) -> str:

        neg = await db_service.db.negotiations.find_one(
            {"influencer_id": influencer_id, "campaign_id": campaign_id}
        )

        if not neg:
            campaign = await db_service.db.influencer_campaigns.find_one(
                {"id": campaign_id}
            )

            neg = NegotiationState(
                influencer_id=influencer_id,
                campaign_id=campaign_id,
                our_budget=campaign["budget_per_influencer"] if campaign else 500,
            ).dict()

            await db_service.db.negotiations.insert_one(neg)

        neg["messages"].append({"role": "them", "content": their_message})

        response_text, new_status = await self._negotiate(neg, their_message)

        neg["messages"].append({"role": "us", "content": response_text})
        neg["status"] = new_status
        neg["round"] += 1
        neg["updated_at"] = datetime.now()

        await db_service.db.negotiations.replace_one(
            {"influencer_id": influencer_id, "campaign_id": campaign_id},
            neg,
        )

        return response_text

    async def _negotiate(self, neg: Dict, their_message: str):

        history = "\n".join(
            f"{m['role']}: {m['content']}" for m in neg.get("messages", [])[-5:]
        )

        prompt = f"""
You are negotiating an influencer deal.

Budget: {neg["our_budget"]}
Round: {neg["round"]}

History:
{history}

Message:
{their_message}

Return JSON:
{{
 "status": "accepted|rejected|countered|pending",
 "our_reply": "reply"
}}
"""

        try:
            text = await self._call_llm(prompt)

            cleaned = text.replace("```json", "").replace("```", "").strip()
            data = json.loads(cleaned)

            return data["our_reply"], data["status"]

        except Exception:
            return "Thanks, we'll get back to you.", "pending"


influencer_outreach = InfluencerOutreach()