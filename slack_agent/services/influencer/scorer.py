import json
from typing import Dict, List

# CHANGE: Import ChatOpenAI from langchain_openai and HumanMessage from langchain_core
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage

from slack_agent.config.settings import settings
from slack_agent.models.schemas import InfluencerCampaign, InfluencerProfile


class InfluencerScorer:
    """
    AI-powered scoring using OpenAI gpt-4o-mini
    """

    def __init__(self):
        # CHANGE: Initialize a ChatOpenAI instance configured specifically for JSON outputs
        self.json_llm = ChatOpenAI(
            model=settings.openai_model,
            api_key=settings.openai_api_key,
            temperature=0.2,
            model_kwargs={"response_format": {"type": "json_object"}},
        )

    async def score_batch(
        self,
        influencers: List[InfluencerProfile],
        campaign: InfluencerCampaign,
        min_score: float = 0.5,
    ) -> List[InfluencerProfile]:

        scored = []

        for inf in influencers:
            if not self._passes_hard_filters(inf, campaign):
                continue

            score = await self._score_influencer(inf, campaign)
            inf.relevance_score = score
            inf.niche = campaign.target_niche

            if score >= min_score:
                scored.append(inf)

        scored.sort(key=lambda x: x.relevance_score or 0, reverse=True)
        return scored

    def _passes_hard_filters(
        self,
        inf: InfluencerProfile,
        campaign: InfluencerCampaign,
    ) -> bool:

        if inf.followers < campaign.min_followers:
            return False

        if campaign.target_tiers and inf.tier not in campaign.target_tiers:
            return False

        if (
            campaign.min_engagement_rate
            & inf.engagement_rate is not None
            & inf.engagement_rate < campaign.min_engagement_rate
        ):
            return False

        if campaign.target_platforms and inf.platform not in campaign.target_platforms:
            return False

        return True

    async def _score_influencer(
        self,
        inf: InfluencerProfile,
        campaign: InfluencerCampaign,
    ) -> float:

        prompt = f"""
You are an influencer marketing expert.

Score this influencer from 0.0 to 1.0.

Product: {campaign.product_name}
Description: {campaign.product_description}
Target niche: {campaign.target_niche}

Influencer:
- Platform: {inf.platform}
- Name: {inf.name}
- Bio: {inf.bio or "N/A"}
- Followers: {inf.followers}
- Engagement: {inf.engagement_rate or "unknown"}
- Topics: {", ".join(inf.tags) if inf.tags else "unknown"}
- Country: {inf.country or "unknown"}

Return ONLY JSON:
{{"score": 0.0}}
"""

        try:
            # CHANGE: Refactored to utilize ainvoke with standard message structures
            response = await self.json_llm.ainvoke([HumanMessage(content=prompt)])
            data = json.loads(response.content.strip())

            return max(0.0, min(1.0, float(data.get("score", 0.0))))

        except Exception as e:
            print(f"Scoring error for {inf.name}: {e}")
            return 0.0

    async def suggest_keywords_for_product(
        self,
        product_name: str,
        product_description: str,
        platforms: List[str],
    ) -> Dict[str, List[str]]:

        prompt = f"""
Suggest influencer search keywords.

Product: {product_name}
Description: {product_description}
Platforms: {", ".join(platforms)}

Return JSON:
{{
  "youtube_keywords": [],
  "instagram_hashtags": []
}}
"""

        try:
            # CHANGE: Replaced legacy HTTP implementation with json_llm invocation
            response = await self.json_llm.ainvoke([HumanMessage(content=prompt)])
            return json.loads(response.content.strip())

        except Exception:
            return {
                "youtube_keywords": [product_name],
                "instagram_hashtags": [product_name.lower().replace(" ", "")],
            }


influencer_scorer = InfluencerScorer()