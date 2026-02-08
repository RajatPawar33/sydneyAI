from typing import Dict, List, Optional

import httpx
from config.settings import settings


class FacebookClient:
    """
    facebook graph api integration
    posts to facebook pages
    """

    def __init__(self):
        self.access_token = getattr(settings, "facebook_access_token", None)
        self.page_id = getattr(settings, "facebook_page_id", None)
        self.base_url = "https://graph.facebook.com/v18.0"

    async def create_post(self, message: str, link: Optional[str] = None) -> Dict:
        # create page post
        if not self.access_token or not self.page_id:
            raise ValueError("facebook credentials not configured")

        # max 63206 chars but keep reasonable
        if len(message) > 5000:
            message = message[:4997] + "..."

        params = {"message": message, "access_token": self.access_token}

        if link:
            params["link"] = link

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/{self.page_id}/feed", params=params
            )

            if response.status_code == 200:
                data = response.json()
                return {"success": True, "post_id": data["id"], "message": message}
            else:
                return {"success": False, "error": response.text}

    async def delete_post(self, post_id: str) -> bool:
        async with httpx.AsyncClient() as client:
            response = await client.delete(
                f"{self.base_url}/{post_id}", params={"access_token": self.access_token}
            )
            return response.status_code == 200

    async def get_page_info(self) -> Optional[Dict]:
        # get page details
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/{self.page_id}",
                params={
                    "fields": "id,name,fan_count,followers_count",
                    "access_token": self.access_token,
                },
            )

            if response.status_code == 200:
                return response.json()
            return None

    async def get_page_posts(self, limit: int = 10) -> List[Dict]:
        # get recent posts
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/{self.page_id}/posts",
                params={
                    "fields": "id,message,created_time,permalink_url",
                    "limit": limit,
                    "access_token": self.access_token,
                },
            )

            if response.status_code == 200:
                return response.json().get("data", [])
            return []


facebook_client = FacebookClient()
