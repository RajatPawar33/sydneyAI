from enum import Enum
from typing import Dict, List, Optional

from services.social.facebook import facebook_client
from services.social.instagram import instagram_client
from services.social.linkedin import linkedin_client
from services.social.twitter import twitter_client


class Platform(str, Enum):
    TWITTER = "twitter"
    LINKEDIN = "linkedin"
    FACEBOOK = "facebook"
    INSTAGRAM = "instagram"


class SocialMediaManager:
    """
    unified interface for all social media platforms
    """

    def __init__(self):
        self.clients = {
            Platform.TWITTER: twitter_client,
            Platform.LINKEDIN: linkedin_client,
            Platform.FACEBOOK: facebook_client,
            Platform.INSTAGRAM: instagram_client,
        }

    async def post_to_platform(
        self, platform: str, content: str, link: Optional[str] = None
    ) -> Dict:
        # route to appropriate client
        platform_enum = Platform(platform.lower())
        client = self.clients.get(platform_enum)

        if not client:
            return {"success": False, "error": f"unsupported platform: {platform}"}

        try:
            if platform_enum == Platform.TWITTER:
                result = await client.create_tweet(content)

            elif platform_enum == Platform.LINKEDIN:
                if link:
                    result = await client.create_post_with_link(content, link)
                else:
                    result = await client.create_post(content)

            elif platform_enum == Platform.FACEBOOK:
                result = await client.create_post(content, link)

            elif platform_enum == Platform.INSTAGRAM:
                result = await client.create_post(content)

            else:
                result = {"success": False, "error": "platform not implemented"}

            return result

        except ValueError as e:
            return {"success": False, "error": str(e)}
        except Exception as e:
            return {"success": False, "error": f"unexpected error: {str(e)}"}

    async def post_to_multiple(
        self, platforms: List[str], content: str, link: Optional[str] = None
    ) -> Dict[str, Dict]:
        # post same content to multiple platforms
        results = {}

        for platform in platforms:
            result = await self.post_to_platform(platform, content, link)
            results[platform] = result

        return results

    async def get_platform_info(self, platform: str) -> Optional[Dict]:
        # get account info for platform
        platform_enum = Platform(platform.lower())
        client = self.clients.get(platform_enum)

        if not client:
            return None

        try:
            if platform_enum == Platform.TWITTER:
                return await client.get_me()
            elif platform_enum == Platform.LINKEDIN:
                return await client.get_profile()
            elif platform_enum == Platform.FACEBOOK:
                return await client.get_page_info()
            elif platform_enum == Platform.INSTAGRAM:
                return await client.get_account_info()
        except Exception as e:
            print(f"error getting {platform} info: {e}")
            return None

    async def validate_platforms(self, platforms: List[str]) -> Dict[str, bool]:
        # check which platforms are properly configured
        results = {}

        for platform in platforms:
            try:
                info = await self.get_platform_info(platform)
                results[platform] = info is not None
            except Exception:
                results[platform] = False

        return results

    def get_platform_character_limits(self) -> Dict[str, int]:
        # return max character limits for each platform
        return {
            Platform.TWITTER: 280,
            Platform.LINKEDIN: 3000,
            Platform.FACEBOOK: 5000,
            Platform.INSTAGRAM: 2200,
        }

    def optimize_content_for_platform(self, content: str, platform: str) -> str:
        # truncate content if exceeds platform limit
        limits = self.get_platform_character_limits()
        platform_enum = Platform(platform.lower())
        limit = limits.get(platform_enum, 1000)

        if len(content) > limit:
            return content[: limit - 3] + "..."

        return content


social_media_manager = SocialMediaManager()
