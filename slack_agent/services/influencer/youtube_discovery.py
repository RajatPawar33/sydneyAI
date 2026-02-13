import asyncio
import re
from typing import Dict, List, Optional

from config.settings import settings
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from models.schemas import InfluencerProfile


class YouTubeDiscovery:
    def __init__(self):
        self.api_key = settings.youtube_api_key
        self._client = None

    def _get_client(self):
        # lazy init — build is sync
        if not self._client:
            if not self.api_key:
                raise ValueError("youtube_api_key not configured")
            self._client = build("youtube", "v3", developerKey=self.api_key)
        return self._client

    async def search_channels(
        self,
        keywords: List[str],
        max_results: int = 50,
        region_code: Optional[str] = None,
        language: Optional[str] = None,
    ) -> List[Dict]:
        # search.list costs 100 quota units per call
        # channels.list costs 1 unit per call — use both in sequence
        youtube = self._get_client()
        channel_ids = set()

        loop = asyncio.get_event_loop()

        for keyword in keywords:
            try:

                def _search(kw=keyword):
                    params = dict(
                        part="snippet",
                        q=kw,
                        type="channel",
                        maxResults=min(max_results, 50),
                        order="relevance",
                    )
                    if region_code:
                        params["regionCode"] = region_code
                    if language:
                        params["relevanceLanguage"] = language
                    return youtube.search().list(**params).execute()

                response = await loop.run_in_executor(None, _search)
                for item in response.get("items", []):
                    channel_ids.add(item["snippet"]["channelId"])
            except HttpError as e:
                print(f"youtube search error for '{keyword}': {e}")

        if not channel_ids:
            return []

        return await self._enrich_channels(list(channel_ids))

    async def _enrich_channels(self, channel_ids: List[str]) -> List[Dict]:
        # channels.list supports up to 50 ids per call — batch them
        youtube = self._get_client()
        loop = asyncio.get_event_loop()
        results = []

        for i in range(0, len(channel_ids), 50):
            batch = channel_ids[i : i + 50]

            def _fetch(ids=batch):
                return (
                    youtube.channels()
                    .list(
                        part="snippet,statistics,brandingSettings,topicDetails",
                        id=",".join(ids),
                    )
                    .execute()
                )

            try:
                response = await loop.run_in_executor(None, _fetch)
                results.extend(response.get("items", []))
            except HttpError as e:
                print(f"youtube channels.list error: {e}")

        return results

    async def get_channel_stats(self, channel_id: str) -> Optional[Dict]:
        rows = await self._enrich_channels([channel_id])
        return rows[0] if rows else None

    def parse_channel(self, raw: Dict) -> InfluencerProfile:
        snippet = raw.get("snippet", {})
        stats = raw.get("statistics", {})
        branding = raw.get("brandingSettings", {}).get("channel", {})

        followers = int(stats.get("subscriberCount", 0))
        total_views = int(stats.get("viewCount", 0))
        video_count = int(stats.get("videoCount", 1)) or 1

        # rough avg views per video
        avg_views = total_views // video_count

        # extract email from description / keywords
        desc = snippet.get("description", "")
        kw = branding.get("keywords", "")
        email = self._extract_email(f"{desc} {kw}")

        channel_id = raw.get("id", "")

        return InfluencerProfile(
            platform="youtube",
            handle=snippet.get("customUrl", channel_id),
            channel_id=channel_id,
            name=snippet.get("title", ""),
            bio=desc[:500] if desc else None,
            email=email,
            followers=followers,
            avg_views=avg_views,
            country=snippet.get("country"),
            profile_url=f"https://youtube.com/channel/{channel_id}",
            tags=self._extract_topics(raw),
        )

    def _extract_email(self, text: str) -> Optional[str]:
        if not text:
            return None
        pattern = r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"
        matches = re.findall(pattern, text)
        # skip generic platform emails
        skip = {"support@", "noreply@", "no-reply@", "help@", "info@youtube"}
        for m in matches:
            if not any(m.startswith(s) for s in skip):
                return m
        return None

    def _extract_topics(self, raw: Dict) -> List[str]:
        topic_data = raw.get("topicDetails", {})
        categories = topic_data.get("topicCategories", [])
        # e.g. https://en.wikipedia.org/wiki/Fashion -> "Fashion"
        return [c.split("/")[-1].replace("_", " ") for c in categories]


youtube_discovery = YouTubeDiscovery()
