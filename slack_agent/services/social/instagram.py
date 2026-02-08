from typing import Dict, List, Optional

import httpx
from config.settings import settings


class InstagramClient:
    """
    instagram graph api integration (business/creator accounts)
    works through facebook graph api
    """

    def __init__(self):
        self.access_token = getattr(settings, "instagram_access_token", None)
        self.instagram_account_id = getattr(settings, "instagram_account_id", None)
        self.base_url = "https://graph.facebook.com/v18.0"

    async def create_post(self, caption: str, is_carousel: bool = False) -> Dict:
        # create text post (caption only - instagram requires media but we keep for future)
        # note: instagram api requires at least one image/video
        # this is placeholder for when media is added later
        if not self.access_token or not self.instagram_account_id:
            raise ValueError("instagram credentials not configured")

        # max 2200 chars for caption
        if len(caption) > 2200:
            caption = caption[:2197] + "..."

        return {
            "success": False,
            "error": "instagram requires media - text-only posts not supported by api",
        }

    async def get_account_info(self) -> Optional[Dict]:
        # get instagram business account info
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/{self.instagram_account_id}",
                params={
                    "fields": "id,username,followers_count,follows_count,media_count",
                    "access_token": self.access_token,
                },
            )

            if response.status_code == 200:
                return response.json()
            return None

    async def get_recent_media(self, limit: int = 10) -> List[Dict]:
        # get recent posts
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/{self.instagram_account_id}/media",
                params={
                    "fields": "id,caption,media_type,media_url,permalink,timestamp",
                    "limit": limit,
                    "access_token": self.access_token,
                },
            )

            if response.status_code == 200:
                return response.json().get("data", [])
            return []

    async def publish_container(self, container_id: str) -> Dict:
        # publish created media container
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/{self.instagram_account_id}/media_publish",
                params={"creation_id": container_id, "access_token": self.access_token},
            )

            if response.status_code == 200:
                data = response.json()
                return {"success": True, "media_id": data["id"]}
            else:
                return {"success": False, "error": response.text}


instagram_client = InstagramClient()
