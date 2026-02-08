from typing import Dict, Optional

import httpx
from config.settings import settings


class LinkedInClient:
    """
    linkedin api integration
    uses oauth 2.0 for authentication
    """

    def __init__(self):
        self.access_token = getattr(settings, "linkedin_access_token", None)
        self.person_id = getattr(settings, "linkedin_person_id", None)
        self.base_url = "https://api.linkedin.com/v2"

    def _get_headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
            "X-Restli-Protocol-Version": "2.0.0",
        }

    async def create_post(self, text: str) -> Dict:
        # create text post (ugcPost)
        if not self.access_token or not self.person_id:
            raise ValueError("linkedin credentials not configured")

        # max 3000 chars for linkedin
        if len(text) > 3000:
            text = text[:2997] + "..."

        payload = {
            "author": f"urn:li:person:{self.person_id}",
            "lifecycleState": "PUBLISHED",
            "specificContent": {
                "com.linkedin.ugc.ShareContent": {
                    "shareCommentary": {"text": text},
                    "shareMediaCategory": "NONE",
                }
            },
            "visibility": {"com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"},
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/ugcPosts", headers=self._get_headers(), json=payload
            )

            if response.status_code == 201:
                post_id = response.headers.get("X-RestLi-Id")
                return {"success": True, "post_id": post_id, "text": text}
            else:
                return {"success": False, "error": response.text}

    async def create_post_with_link(
        self, text: str, link_url: str, link_title: str = ""
    ) -> Dict:
        # post with link preview
        if not self.access_token or not self.person_id:
            raise ValueError("linkedin credentials not configured")

        payload = {
            "author": f"urn:li:person:{self.person_id}",
            "lifecycleState": "PUBLISHED",
            "specificContent": {
                "com.linkedin.ugc.ShareContent": {
                    "shareCommentary": {"text": text},
                    "shareMediaCategory": "ARTICLE",
                    "media": [
                        {
                            "status": "READY",
                            "originalUrl": link_url,
                            "title": {"text": link_title or link_url},
                        }
                    ],
                }
            },
            "visibility": {"com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"},
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/ugcPosts", headers=self._get_headers(), json=payload
            )

            if response.status_code == 201:
                post_id = response.headers.get("X-RestLi-Id")
                return {"success": True, "post_id": post_id, "text": text}
            else:
                return {"success": False, "error": response.text}

    async def get_profile(self) -> Optional[Dict]:
        # get user profile
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/me", headers=self._get_headers()
            )

            if response.status_code == 200:
                return response.json()
            return None


linkedin_client = LinkedInClient()
