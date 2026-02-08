from typing import Dict, Optional

import httpx
from config.settings import settings


class TwitterClient:
    """
    twitter/x api v2 integration
    uses oauth 2.0 for authentication
    """

    def __init__(self):
        self.api_key = getattr(settings, "twitter_api_key", None)
        self.api_secret = getattr(settings, "twitter_api_secret", None)
        self.access_token = getattr(settings, "twitter_access_token", None)
        self.access_token_secret = getattr(
            settings, "twitter_access_token_secret", None
        )
        self.bearer_token = getattr(settings, "twitter_bearer_token", None)
        self.base_url = "https://api.twitter.com/2"

    def _get_headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.bearer_token}",
            "Content-Type": "application/json",
        }

    async def create_tweet(self, text: str) -> Dict:
        # post tweet
        if not self.bearer_token:
            raise ValueError("twitter bearer token not configured")

        if len(text) > 280:
            text = text[:277] + "..."

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/tweets",
                headers=self._get_headers(),
                json={"text": text},
            )

            if response.status_code == 201:
                data = response.json()
                return {
                    "success": True,
                    "tweet_id": data["data"]["id"],
                    "text": data["data"]["text"],
                }
            else:
                return {"success": False, "error": response.text}

    async def delete_tweet(self, tweet_id: str) -> bool:
        async with httpx.AsyncClient() as client:
            response = await client.delete(
                f"{self.base_url}/tweets/{tweet_id}", headers=self._get_headers()
            )
            return response.status_code == 200

    async def get_me(self) -> Optional[Dict]:
        # get authenticated user info
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/users/me", headers=self._get_headers()
            )

            if response.status_code == 200:
                return response.json()["data"]
            return None


twitter_client = TwitterClient()
