import asyncio
import re
from typing import Dict, List, Optional

import httpx

from slack_agent.config.settings import settings
from slack_agent.models.schemas import InfluencerProfile


class InstagramDiscovery:
    """
    uses apify's instagram-profile-scraper actor to get public profile data
    apify free tier: $5/month credit (~20k lightweight scrapes)
    pay-per-use: ~$0.25 per 1000 results
    actor id: apify/instagram-profile-scraper
    """

    def __init__(self):
        self.api_token = settings.apify_api_token
        self.base_url = "https://api.apify.com/v2"
        # actor that searches hashtags and returns profiles
        self.hashtag_actor = "apify/instagram-hashtag-scraper"
        # actor that scrapes individual profiles by username
        self.profile_actor = "apify/instagram-profile-scraper"

    async def _run_actor(
        self, actor_id: str, input_data: Dict, timeout: int = 120
    ) -> List[Dict]:
        # trigger actor run and poll until complete
        if not self.api_token:
            raise ValueError("apify_api_token not configured")

        async with httpx.AsyncClient(timeout=timeout) as client:
            # start run
            run_resp = await client.post(
                f"{self.base_url}/acts/{actor_id}/runs",
                params={"token": self.api_token},
                json=input_data,
            )

            if run_resp.status_code != 201:
                print(f"apify actor start failed: {run_resp.text}")
                return []

            run_data = run_resp.json()
            run_id = run_data["data"]["id"]
            dataset_id = run_data["data"]["defaultDatasetId"]

            # poll for completion
            for _ in range(30):
                await asyncio.sleep(4)
                status_resp = await client.get(
                    f"{self.base_url}/actor-runs/{run_id}",
                    params={"token": self.api_token},
                )
                status = status_resp.json()["data"]["status"]
                if status == "SUCCEEDED":
                    break
                if status in ("FAILED", "ABORTED", "TIMED-OUT"):
                    print(f"apify run {run_id} ended with: {status}")
                    return []

            # fetch results
            dataset_resp = await client.get(
                f"{self.base_url}/datasets/{dataset_id}/items",
                params={"token": self.api_token, "format": "json"},
            )

            if dataset_resp.status_code == 200:
                return dataset_resp.json()
            return []

    async def search_by_hashtags(
        self,
        hashtags: List[str],
        max_results_per_tag: int = 20,
    ) -> List[Dict]:
        # scrape top posts per hashtag and collect unique author profiles
        all_profiles: Dict[str, Dict] = {}

        for tag in hashtags:
            raw_tag = tag.lstrip("#")
            items = await self._run_actor(
                self.hashtag_actor,
                {
                    "hashtags": [raw_tag],
                    "resultsLimit": max_results_per_tag,
                },
            )

            for post in items:
                owner = post.get("ownerUsername") or post.get("ownerId")
                if owner and owner not in all_profiles:
                    all_profiles[owner] = {
                        "username": owner,
                        "followers_count": post.get("likesCount", 0),
                    }

        if not all_profiles:
            return []

        # enrich with full profile data in batches of 20
        usernames = list(all_profiles.keys())
        enriched = []

        for i in range(0, len(usernames), 20):
            batch = usernames[i : i + 20]
            profiles = await self._run_actor(
                self.profile_actor,
                {"usernames": batch},
            )
            enriched.extend(profiles)

        return enriched

    async def get_profile(self, username: str) -> Optional[Dict]:
        profiles = await self._run_actor(
            self.profile_actor,
            {"usernames": [username]},
        )
        return profiles[0] if profiles else None

    def parse_profile(self, raw: Dict) -> InfluencerProfile:
        username = raw.get("username", "")
        followers = int(raw.get("followersCount", 0))

        # engagement: (likes + comments) / followers
        avg_likes = raw.get("avgLikes") or raw.get("avgEngagement") or 0
        avg_comments = raw.get("avgComments", 0)
        engagement_rate = None
        if followers > 0:
            engagement_rate = round((avg_likes + avg_comments) / followers, 4)

        bio = raw.get("biography", "")
        email = self._extract_email(bio)

        return InfluencerProfile(
            platform="instagram",
            handle=username,
            channel_id=raw.get("id", username),
            name=raw.get("fullName", username),
            bio=bio[:500] if bio else None,
            email=email,
            followers=followers,
            engagement_rate=engagement_rate,
            country=raw.get("country"),
            profile_url=f"https://instagram.com/{username}",
            tags=self._extract_hashtags(bio),
        )

    def _extract_email(self, text: str) -> Optional[str]:
        if not text:
            return None
        pattern = r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"
        matches = re.findall(pattern, text)
        return matches[0] if matches else None

    def _extract_hashtags(self, bio: str) -> List[str]:
        if not bio:
            return []
        return re.findall(r"#(\w+)", bio)


instagram_discovery = InstagramDiscovery()
