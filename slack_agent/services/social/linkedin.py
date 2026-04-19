from typing import Dict, Optional

import httpx
from config.settings import settings


class LinkedInClient:

    def __init__(self):
        self.access_token = getattr(settings, "linkedin_access_token", None)
        self.person_id = getattr(settings, "linkedin_person_id", None)
        self.base_url = "https://api.linkedin.com/v2"

        if not self.access_token:
            raise ValueError("LinkedIn access token missing")

        if not self.person_id:
            raise ValueError("LinkedIn person ID missing")

        if not self.person_id.startswith("urn:li:member:"):
            raise ValueError(
                f"Invalid LinkedIn person URN: {self.person_id} "
                "(Expected format: urn:li:member:<id>)"
            )

    def _get_headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
            "X-Restli-Protocol-Version": "2.0.0",
        }

    async def create_post(self, text: str) -> Dict:
        
        if len(text) > 3000:
            text = text[:2997] + "..."

        payload = {
            "author": self.person_id,  
            "lifecycleState": "PUBLISHED",
            "specificContent": {
                "com.linkedin.ugc.ShareContent": {
                    "shareCommentary": {"text": text},
                    "shareMediaCategory": "NONE",
                }
            },
            "visibility": {
                "com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"
            },
        }

       
        print("Posting to LinkedIn with author:", self.person_id)

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/ugcPosts",
                headers=self._get_headers(),
                json=payload,
            )

            if response.status_code == 201:
                post_id = response.headers.get("X-RestLi-Id")
                return {
                    "success": True,
                    "post_id": post_id,
                    "text": text,
                }
            else:
                return {
                    "success": False,
                    "status_code": response.status_code,
                    "error": response.text,
                }

    async def create_post_with_link(
        self, text: str, link_url: str, link_title: str = ""
    ) -> Dict:
        """
        Create a post with a link preview
        """

        payload = {
            "author": self.person_id,  
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
            "visibility": {
                "com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"
            },
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/ugcPosts",
                headers=self._get_headers(),
                json=payload,
            )

            if response.status_code == 201:
                post_id = response.headers.get("X-RestLi-Id")
                return {
                    "success": True,
                    "post_id": post_id,
                    "text": text,
                }
            else:
                return {
                    "success": False,
                    "status_code": response.status_code,
                    "error": response.text,
                }

    async def get_profile(self) -> Optional[Dict]:
        

        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/me",
                headers=self._get_headers(),
            )

            print("LinkedIn /me status:", response.status_code)
            print("LinkedIn /me response:", response.text)

            if response.status_code == 200:
                return response.json()

            return None


linkedin_client = LinkedInClient()