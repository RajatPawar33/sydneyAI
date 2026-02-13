import json
from datetime import datetime
from typing import Dict, List, Optional

from config.settings import settings
from langchain_core.messages import HumanMessage
from langchain_openai import ChatOpenAI
from models.schemas import (
    InfluencerCampaign,
    InfluencerProfile,
    InfluencerStatus,
    NegotiationState,
)
from services.database import db_service
from services.email import mailgun_client


class InfluencerOutreach:
    def __init__(self):
        self.llm = ChatOpenAI(
            model=settings.openai_model,
            temperature=0.7,
            max_tokens=800,
            api_key=settings.openai_api_key,
        )

    # --- outreach email generation ---

    async def generate_outreach_email(
        self,
        influencer: InfluencerProfile,
        campaign: InfluencerCampaign,
    ) -> Dict[str, str]:
        prompt = f"""write a personalized influencer outreach email

influencer:
- name: {influencer.name}
- platform: {influencer.platform}
- niche: {", ".join(influencer.tags) if influencer.tags else campaign.target_niche}
- followers: {influencer.followers:,}

product:
- name: {campaign.product_name}
- description: {campaign.product_description}
- budget range: up to ${campaign.budget_per_influencer}

rules:
- subject line under 60 chars, personalized
- body under 200 words
- professional but warm tone
- mention their specific niche/content style
- clearly state we are attaching product details
- ask them to reply to discuss collaboration
- do not mention exact budget in first email

respond ONLY as json:
{{"subject": "...", "body": "..."}}"""

        try:
            response = await self.llm.ainvoke([HumanMessage(content=prompt)])
            text = (
                response.content.strip()
                .replace("```json", "")
                .replace("```", "")
                .strip()
            )
            return json.loads(text)
        except Exception:
            return {
                "subject": f"Collaboration opportunity with {campaign.product_name}",
                "body": f"Hi {influencer.name},\n\nWe'd love to collaborate with you to promote {campaign.product_name}. Please find our product details attached.\n\nLooking forward to your reply!",
            }

    async def send_outreach(
        self,
        influencer: InfluencerProfile,
        campaign: InfluencerCampaign,
        attachment_paths: Optional[List[str]] = None,
    ) -> bool:
        if not influencer.email:
            return False

        email_content = await self.generate_outreach_email(influencer, campaign)

        # use first attachment if exists, otherwise plain email
        attach_paths = attachment_paths or campaign.product_attachment_paths

        if attach_paths:
            # send with first attachment — mailgun supports multiple but keep simple
            result = await mailgun_client.send_with_attachment(
                to=influencer.email,
                subject=email_content["subject"],
                text=email_content["body"],
                attachment_path=attach_paths[0],
                tags=[campaign.id, "influencer_outreach"],
            )
        else:
            result = await mailgun_client.send(
                to=influencer.email,
                subject=email_content["subject"],
                text=email_content["body"],
                tags=[campaign.id, "influencer_outreach"],
            )

        if result.get("success"):
            # update influencer status
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

    # --- negotiation state machine ---

    async def handle_reply(
        self,
        influencer_id: str,
        campaign_id: str,
        their_message: str,
    ) -> str:
        # fetch negotiation state
        neg = await db_service.db.negotiations.find_one(
            {"influencer_id": influencer_id, "campaign_id": campaign_id}
        )

        if not neg:
            # first reply — create negotiation record
            campaign = await db_service.db.influencer_campaigns.find_one(
                {"id": campaign_id}
            )
            neg = NegotiationState(
                influencer_id=influencer_id,
                campaign_id=campaign_id,
                our_budget=campaign["budget_per_influencer"] if campaign else 500.0,
            ).dict()
            await db_service.db.negotiations.insert_one(neg)

        # update message history
        neg["messages"].append({"role": "them", "content": their_message})

        # ask ai to interpret and generate our response
        response_text, new_status = await self._negotiate(neg, their_message)

        neg["messages"].append({"role": "us", "content": response_text})
        neg["status"] = new_status
        neg["round"] += 1
        neg["updated_at"] = datetime.now()

        await db_service.db.negotiations.replace_one(
            {"influencer_id": influencer_id, "campaign_id": campaign_id},
            neg,
        )

        # update influencer status
        inf_status = InfluencerStatus.NEGOTIATING
        if new_status == "accepted":
            inf_status = InfluencerStatus.AGREED
        elif new_status == "rejected":
            inf_status = InfluencerStatus.REJECTED

        await db_service.db.influencers.update_one(
            {"id": influencer_id},
            {"$set": {"status": inf_status}},
        )

        return response_text

    async def _negotiate(
        self,
        neg: Dict,
        their_message: str,
    ) -> tuple[str, str]:
        history_text = "\n".join(
            f"{m['role'].upper()}: {m['content']}" for m in neg.get("messages", [])[-6:]
        )

        prompt = f"""you are negotiating an influencer marketing deal on behalf of a brand

our max budget: ${neg["our_budget"]}
negotiation round: {neg["round"]}
conversation history:
{history_text}

their latest message: "{their_message}"

your task:
1. determine if they: accepted | rejected | made counter-offer | asked a question | interested but unclear
2. respond professionally to move toward deal closure
3. if they ask for budget: start at 70% of our max, negotiate up to 95% max
4. if round > 3 and no deal: politely close conversation
5. if accepted: confirm the deal and outline next steps (content brief, timeline)

respond ONLY as json:
{{
  "status": "accepted|rejected|countered|pending",
  "our_reply": "reply text under 150 words"
}}"""

        try:
            response = await self.llm.ainvoke([HumanMessage(content=prompt)])
            text = (
                response.content.strip()
                .replace("```json", "")
                .replace("```", "")
                .strip()
            )
            data = json.loads(text)
            return data.get("our_reply", "Thank you for your reply."), data.get(
                "status", "pending"
            )
        except Exception:
            return "Thank you for your reply. We'll get back to you shortly.", "pending"

    # --- onboarding ---

    async def send_onboarding_email(
        self,
        influencer: InfluencerProfile,
        campaign: InfluencerCampaign,
        agreed_budget: float,
        attachment_paths: Optional[List[str]] = None,
    ) -> bool:
        subject = f"Welcome aboard! {campaign.product_name} collaboration details"

        body = f"""Hi {influencer.name},

We're thrilled to have you on board for the {campaign.product_name} campaign!

Agreed compensation: ${agreed_budget}

What happens next:
1. Content brief is attached to this email
2. Please review and confirm the key messages
3. Submit your content draft within 7 days for review
4. Upon approval, we'll process payment within 3 business days

Product details and assets are attached. Please don't hesitate to reach out if you have any questions.

Looking forward to creating great content together!"""

        attach_paths = attachment_paths or campaign.product_attachment_paths

        if attach_paths:
            result = await mailgun_client.send_with_attachment(
                to=influencer.email,
                subject=subject,
                text=body,
                attachment_path=attach_paths[0],
                tags=[campaign.id, "influencer_onboarding"],
            )
        else:
            result = await mailgun_client.send(
                to=influencer.email,
                subject=subject,
                text=body,
                tags=[campaign.id, "influencer_onboarding"],
            )

        if result.get("success"):
            await db_service.db.influencers.update_one(
                {"id": influencer.id},
                {"$set": {"status": InfluencerStatus.ONBOARDED}},
            )
            return True

        return False


influencer_outreach = InfluencerOutreach()
