import json
from typing import Dict, List

from langchain_core.messages import HumanMessage
from langchain_openai import ChatOpenAI

from slack_agent.config.settings import settings
from slack_agent.models.schemas import InfluencerCampaign, InfluencerProfile


class InfluencerScorer:
    """
    ai-powered scoring to match influencers to product/campaign
    assigns 0-1 relevance score and filters out bad fits
    """

    def __init__(self):
        self.llm = ChatOpenAI(
            model=settings.openai_model,
            temperature=0.2,  # low temp — scoring should be deterministic
            max_tokens=500,
            api_key=settings.openai_api_key,
        )

    async def score_batch(
        self,
        influencers: List[InfluencerProfile],
        campaign: InfluencerCampaign,
        min_score: float = 0.5,
    ) -> List[InfluencerProfile]:
        # score all influencers and return filtered + sorted list
        scored = []

        for inf in influencers:
            # hard filter first — no api cost
            if not self._passes_hard_filters(inf, campaign):
                continue

            score = await self._score_influencer(inf, campaign)
            inf.relevance_score = score
            inf.niche = campaign.target_niche

            if score >= min_score:
                scored.append(inf)

        # sort by score descending
        scored.sort(key=lambda x: x.relevance_score or 0, reverse=True)
        return scored

    def _passes_hard_filters(
        self,
        inf: InfluencerProfile,
        campaign: InfluencerCampaign,
    ) -> bool:
        # follower count
        if inf.followers < campaign.min_followers:
            return False

        # tier filter
        if campaign.target_tiers and inf.tier not in campaign.target_tiers:
            return False

        # engagement rate filter
        if (
            campaign.min_engagement_rate
            and inf.engagement_rate is not None
            and inf.engagement_rate < campaign.min_engagement_rate
        ):
            return False

        # platform filter
        if campaign.target_platforms and inf.platform not in campaign.target_platforms:
            return False

        return True

    async def _score_influencer(
        self,
        inf: InfluencerProfile,
        campaign: InfluencerCampaign,
    ) -> float:
        prompt = f"""you are an influencer marketing expert
score this influencer for the given product campaign on a scale of 0.0 to 1.0

product: {campaign.product_name}
product description: {campaign.product_description}
target niche: {campaign.target_niche}

influencer:
- platform: {inf.platform}
- name: {inf.name}
- bio: {inf.bio or "not available"}
- followers: {inf.followers:,}
- engagement rate: {inf.engagement_rate or "unknown"}
- topics: {", ".join(inf.tags) if inf.tags else "unknown"}
- country: {inf.country or "unknown"}

scoring criteria:
- niche relevance to product (40%)
- audience size fit for campaign tier (20%)
- engagement quality (20%)
- content authenticity signals from bio (20%)

respond ONLY with a json object:
{{"score": 0.0, "reason": "brief reason under 20 words"}}"""

        try:
            response = await self.llm.ainvoke([HumanMessage(content=prompt)])
            text = response.content.strip()
            # strip any markdown fences
            text = text.replace("```json", "").replace("```", "").strip()
            data = json.loads(text)
            return max(0.0, min(1.0, float(data.get("score", 0.0))))
        except Exception as e:
            print(f"scoring error for {inf.handle}: {e}")
            return 0.0

    async def suggest_keywords_for_product(
        self,
        product_name: str,
        product_description: str,
        platforms: List[str],
    ) -> Dict[str, List[str]]:
        # generate search keywords and hashtags per platform from product info
        prompt = f"""given this product, suggest search terms to find relevant influencers

product: {product_name}
description: {product_description}
platforms: {", ".join(platforms)}

respond ONLY with json:
{{
  "youtube_keywords": ["keyword1", "keyword2", ...],
  "instagram_hashtags": ["hashtag1", "hashtag2", ...]
}}

rules:
- youtube_keywords: 5-8 niche channel search terms (no hashtags)
- instagram_hashtags: 8-12 hashtags without # symbol
- focus on niche content creators not just product category"""

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
            # fallback
            return {
                "youtube_keywords": [product_name, f"{product_name} review"],
                "instagram_hashtags": [product_name.lower().replace(" ", "")],
            }


influencer_scorer = InfluencerScorer()
