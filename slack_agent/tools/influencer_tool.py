import asyncio
from typing import Dict, List, Optional

from slack_agent.models.schemas import (
    InfluencerCampaign,
    InfluencerProfile,
)
from slack_agent.services.database import db_service
from slack_agent.services.influencer.instagram_discovery import instagram_discovery
from slack_agent.services.influencer.outreach import influencer_outreach
from slack_agent.services.influencer.scorer import influencer_scorer
from slack_agent.services.influencer.youtube_discovery import youtube_discovery


class InfluencerTool:
    """
    orchestrates all 4 influencer pipeline steps:
    1. discover  → search youtube + instagram for profiles
    2. score     → ai ranks by relevance to product
    3. outreach  → send personalised emails with attachments
    4. negotiate → handle replies, auto-negotiate budget, onboard
    """

    # --- step 1: discover ---

    async def discover(self, campaign: InfluencerCampaign) -> List[InfluencerProfile]:
        # generate platform-specific search terms from product info
        keyword_map = await influencer_scorer.suggest_keywords_for_product(
            product_name=campaign.product_name,
            product_description=campaign.product_description,
            platforms=campaign.target_platforms,
        )

        tasks = []

        if "youtube" in campaign.target_platforms:
            tasks.append(
                self._discover_youtube(
                    keyword_map.get("youtube_keywords", [campaign.product_name]),
                    campaign.min_followers,
                )
            )

        if "instagram" in campaign.target_platforms:
            tasks.append(
                self._discover_instagram(
                    keyword_map.get("instagram_hashtags", []),
                )
            )

        results = await asyncio.gather(*tasks, return_exceptions=True)
        all_profiles: List[InfluencerProfile] = []

        for r in results:
            if isinstance(r, list):
                all_profiles.extend(r)

        # deduplicate by handle+platform
        seen = set()
        unique = []
        for p in all_profiles:
            key = f"{p.platform}:{p.handle}"
            if key not in seen:
                seen.add(key)
                unique.append(p)

        return unique

    async def _discover_youtube(
        self,
        keywords: List[str],
        min_followers: int,
    ) -> List[InfluencerProfile]:
        raw_channels = await youtube_discovery.search_channels(keywords, max_results=50)
        profiles = [youtube_discovery.parse_channel(c) for c in raw_channels]
        # filter by min followers
        return [p for p in profiles if p.followers >= min_followers]

    async def _discover_instagram(self, hashtags: List[str]) -> List[InfluencerProfile]:
        if not hashtags:
            return []
        raw_profiles = await instagram_discovery.search_by_hashtags(
            hashtags, max_results_per_tag=20
        )
        return [instagram_discovery.parse_profile(p) for p in raw_profiles]

    # --- step 2: score + filter ---

    async def score_and_filter(
        self,
        profiles: List[InfluencerProfile],
        campaign: InfluencerCampaign,
        min_score: float = 0.55,
    ) -> List[InfluencerProfile]:
        return await influencer_scorer.score_batch(profiles, campaign, min_score)

    # --- step 3: save + outreach ---

    async def save_influencers(
        self,
        profiles: List[InfluencerProfile],
        campaign: InfluencerCampaign,
    ) -> int:
        saved = 0
        for p in profiles:
            existing = await db_service.db.influencers.find_one(
                {"platform": p.platform, "handle": p.handle}
            )
            if not existing:
                doc = p.dict()
                await db_service.db.influencers.insert_one(doc)
                saved += 1

        # add influencer ids to campaign
        handles = [p.id for p in profiles]
        await db_service.db.influencer_campaigns.update_one(
            {"id": campaign.id},
            {"$addToSet": {"influencer_ids": {"$each": handles}}},
        )

        return saved

    async def run_outreach_batch(
        self,
        campaign: InfluencerCampaign,
        profiles: List[InfluencerProfile],
        limit: int = 20,
    ) -> Dict[str, int]:
        # only contact influencers with email addresses
        contactable = [p for p in profiles if p.email][:limit]
        results = {
            "sent": 0,
            "skipped_no_email": len(profiles) - len(contactable),
            "failed": 0,
        }

        for influencer in contactable:
            success = await influencer_outreach.send_outreach(
                influencer=influencer,
                campaign=campaign,
            )
            if success:
                results["sent"] += 1
            else:
                results["failed"] += 1

        return results

    # --- step 4: negotiate + onboard ---

    async def process_reply(
        self,
        influencer_handle: str,
        platform: str,
        campaign_id: str,
        their_message: str,
    ) -> str:
        inf_doc = await db_service.db.influencers.find_one(
            {"handle": influencer_handle, "platform": platform}
        )
        if not inf_doc:
            return "influencer not found in database"

        influencer = InfluencerProfile(**inf_doc)
        reply = await influencer_outreach.handle_reply(
            influencer_id=influencer.id,
            campaign_id=campaign_id,
            their_message=their_message,
        )
        return reply

    async def onboard_influencer(
        self,
        influencer_handle: str,
        platform: str,
        campaign_id: str,
        agreed_budget: float,
    ) -> bool:
        inf_doc = await db_service.db.influencers.find_one(
            {"handle": influencer_handle, "platform": platform}
        )
        campaign_doc = await db_service.db.influencer_campaigns.find_one(
            {"id": campaign_id}
        )

        if not inf_doc or not campaign_doc:
            return False

        influencer = InfluencerProfile(**inf_doc)
        campaign = InfluencerCampaign(**campaign_doc)

        return await influencer_outreach.send_onboarding_email(
            influencer=influencer,
            campaign=campaign,
            agreed_budget=agreed_budget,
        )

    # --- full pipeline ---

    async def run_full_pipeline(
        self,
        campaign: InfluencerCampaign,
        outreach_limit: int = 20,
        min_score: float = 0.55,
    ) -> Dict:
        # step 1: discover
        profiles = await self.discover(campaign)

        # step 2: score + filter
        scored = await self.score_and_filter(profiles, campaign, min_score)

        # step 3: save to db
        saved = await self.save_influencers(scored, campaign)

        # step 4: outreach
        outreach_results = await self.run_outreach_batch(
            campaign, scored, outreach_limit
        )

        return {
            "discovered": len(profiles),
            "qualified": len(scored),
            "saved_to_db": saved,
            "outreach": outreach_results,
            "top_influencers": [
                {
                    "name": p.name,
                    "platform": p.platform,
                    "handle": p.handle,
                    "followers": p.followers,
                    "score": p.relevance_score,
                    "has_email": bool(p.email),
                }
                for p in scored[:10]
            ],
        }

    # --- query helpers ---

    async def get_campaign_influencers(
        self,
        campaign_id: str,
        status_filter: Optional[str] = None,
    ) -> List[Dict]:
        campaign = await db_service.db.influencer_campaigns.find_one(
            {"id": campaign_id}
        )
        if not campaign:
            return []

        query: Dict = {"id": {"$in": campaign.get("influencer_ids", [])}}
        if status_filter:
            query["status"] = status_filter

        cursor = db_service.db.influencers.find(query)
        return await cursor.to_list(length=None)

    async def get_pipeline_stats(self, campaign_id: str) -> Dict:
        influencers = await self.get_campaign_influencers(campaign_id)
        stats: Dict[str, int] = {}

        for inf in influencers:
            status = inf.get("status", "unknown")
            stats[status] = stats.get(status, 0) + 1

        total = len(influencers)
        return {
            "total": total,
            "by_status": stats,
            "contacted_rate": round(
                (
                    stats.get("contacted", 0)
                    + stats.get("negotiating", 0)
                    + stats.get("agreed", 0)
                    + stats.get("onboarded", 0)
                )
                / max(total, 1)
                * 100,
                1,
            ),
            "onboarded": stats.get("onboarded", 0),
        }


influencer_tool = InfluencerTool()
