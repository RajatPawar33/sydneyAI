from datetime import datetime
from typing import Dict

from config.settings import settings
from core.agent import ai_agent
from models.schemas import DateRangeQuery, EmailRecipient
from services.cache import cache_service
from services.database import db_service
from slack_bolt.async_app import AsyncApp
from tools.marketing_tools import outreach_tool, scheduling_tool, social_media_tool
from utils.helpers import (
    clean_slack_text,
    format_slack_message,
    parse_date_from_text,
    parse_date_range_from_text,
)


class SlackHandler:
    def __init__(self, app: AsyncApp):
        self.app = app
        self.bot_user_id = settings.bot_user_id
        self._register_handlers()

    def _register_handlers(self):
        # event handlers
        self.app.event("app_mention")(self.handle_mention)
        self.app.message("")(self.handle_direct_message)
        self.app.event("message")(self.handle_message_events)

        # command handlers
        self.app.command("/ai-help")(self.handle_help_command)
        self.app.command("/schedule-post")(self.handle_schedule_post_command)
        self.app.command("/send-campaign")(self.handle_send_campaign_command)

    async def handle_mention(self, event: Dict, say, client):
        try:
            user_id = event["user"]
            channel_id = event["channel"]
            text = event["text"]
            thread_ts = event.get("thread_ts", event["ts"])

            # check rate limit
            if not await cache_service.check_rate_limit(user_id):
                await say(
                    text="rate limit exceeded, please wait a moment",
                    thread_ts=thread_ts,
                )
                return

            # show typing indicator
            typing_msg = await client.chat_postMessage(
                channel=channel_id, thread_ts=thread_ts, text="thinking... 🤔"
            )

            # get user and channel info
            user_info = await self._get_user_info(client, user_id)
            channel_info = await self._get_channel_info(client, channel_id)

            # clean message
            clean_text = clean_slack_text(text, self.bot_user_id)

            # get conversation history
            conv_history = await db_service.get_conversation_history(user_id, limit=5)

            # check for special commands
            response_text = await self._process_command(
                clean_text, user_info, channel_info, conv_history
            )

            # delete typing indicator
            await client.chat_delete(channel=channel_id, ts=typing_msg["ts"])

            # send response
            await say(text=format_slack_message(response_text), thread_ts=thread_ts)

            # save conversation
            await db_service.save_conversation(
                user_id=user_id,
                channel_id=channel_id,
                message=clean_text,
                response=response_text,
            )

        except Exception as e:
            print(f"error handling mention: {e}")
            await say(
                text=f"error: {str(e)}", thread_ts=event.get("thread_ts", event["ts"])
            )

    async def handle_direct_message(self, message: Dict, say, client):
        try:
            # only dm's
            if message.get("channel_type") != "im":
                return

            if message.get("bot_id"):
                return

            user_id = message["user"]
            text = message["text"]

            # check rate limit
            if not await cache_service.check_rate_limit(user_id):
                await say("rate limit exceeded")
                return

            # typing indicator
            typing_msg = await client.chat_postMessage(
                channel=message["channel"], text="thinking... 🤔"
            )

            user_info = await self._get_user_info(client, user_id)
            conv_history = await db_service.get_conversation_history(user_id)

            response_text = await self._process_command(
                text,
                user_info,
                {"name": "direct-message", "id": message["channel"]},
                conv_history,
            )

            await client.chat_delete(channel=message["channel"], ts=typing_msg["ts"])

            await say(format_slack_message(response_text))

            await db_service.save_conversation(
                user_id=user_id,
                channel_id=message["channel"],
                message=text,
                response=response_text,
            )

        except Exception as e:
            print(f"error in dm: {e}")
            await say(f"error: {str(e)}")

    async def handle_message_events(self, body, logger):
        logger.debug(body)

    async def handle_help_command(self, ack, respond):
        await ack()

        help_text = """*ai marketing manager - help* 🤖

*usage:*
• mention me: `@bot your question`
• dm me directly
• use slash commands

*capabilities:*
• email outreach campaigns
• schedule social media posts
• generate marketing content
• collect customer data
• marketing strategy advice

*commands:*
• `/ai-help` - show this help
• `/schedule-post` - schedule social post
• `/send-campaign` - send email campaign

*examples:*
• "collect emails from last 30 days with min 2 orders"
• "generate instagram post about our new product"
• "schedule post for tomorrow 3pm"
• "create promotional email for summer sale"
"""

        await respond(help_text)

    async def handle_schedule_post_command(self, ack, respond, command):
        await ack()
        # placeholder for interactive form
        await respond("feature coming soon - use natural language with @bot for now")

    async def handle_send_campaign_command(self, ack, respond, command):
        await ack()
        await respond("feature coming soon - use natural language with @bot for now")

    async def _process_command(
        self, text: str, user_info: Dict, channel_info: Dict, conv_history: list
    ) -> str:
        text_lower = text.lower()

        # handle outreach commands
        if any(
            word in text_lower
            for word in ["collect email", "get email", "customer email"]
        ):
            return await self._handle_email_collection(text, user_info)

        # handle scheduling commands
        if "schedule" in text_lower and (
            "post" in text_lower or "message" in text_lower
        ):
            return await self._handle_schedule_post(text, user_info)

        # handle immediate posting
        if any(word in text_lower for word in ["post now", "publish now"]) and any(
            word in text_lower
            for word in ["twitter", "linkedin", "facebook", "instagram"]
        ):
            return await self._handle_schedule_post(text, user_info)

        # check social media accounts
        if "check accounts" in text_lower or "verify platforms" in text_lower:
            return await self._handle_check_accounts()

        # handle campaign creation
        if "campaign" in text_lower or "send email" in text_lower:
            return await self._handle_create_campaign(text, user_info)

        # default ai response
        response = await ai_agent.run(
            message=text,
            user_info=user_info,
            channel_info=channel_info,
            conversation_history=conv_history,
        )

        return response.content

    async def _handle_email_collection(self, text: str, user_info: Dict) -> str:
        try:
            # parse date range
            date_range = parse_date_range_from_text(text)

            # parse min orders
            import re

            min_orders = 0
            match = re.search(r"(?:min|minimum|at least)\s+(\d+)\s+order", text.lower())
            if match:
                min_orders = int(match.group(1))

            # determine source
            source = "shopify" if "shopify" in text.lower() else "database"

            # collect emails
            date_range_obj = None
            if date_range:
                date_range_obj = DateRangeQuery(**date_range)

            recipients = await outreach_tool.collect_customer_emails(
                source=source, date_range=date_range_obj, min_orders=min_orders
            )

            if not recipients:
                return "no customers found matching criteria"

            # cache for next step
            await cache_service.set(
                f"recipients:{user_info['id']}",
                [r.dict() for r in recipients],
                expire=1800,
            )

            return f"""found {len(recipients)} customers
filters applied:
• source: {source}
• date range: {date_range or "all time"}
• min orders: {min_orders}

next steps:
1. generate email content
2. create campaign
3. schedule or send

say "generate promotional email for [topic]" to continue"""

        except Exception as e:
            return f"error collecting emails: {str(e)}"

    async def _handle_schedule_post(self, text: str, user_info: Dict) -> str:
        try:
            # parse platforms
            platforms = []
            text_lower = text.lower()

            for p in ["twitter", "linkedin", "facebook", "instagram"]:
                if p in text_lower:
                    platforms.append(p)

            if not platforms:
                platforms = ["twitter"]  # default

            # check if posting now or scheduling
            is_immediate = any(
                word in text_lower
                for word in ["post now", "publish now", "immediately"]
            )

            # parse scheduled time (if not immediate)
            scheduled_at = None
            if not is_immediate:
                scheduled_at = parse_date_from_text(text)
                if not scheduled_at:
                    return "couldn't parse schedule time, please specify (e.g., 'tomorrow 3pm') or say 'post now'"

            # generate content
            from services.social_media_manager import social_media_manager

            content = await social_media_tool.generate_post_content(
                platform=platforms[0],  # generate for first platform
                topic=text,
                tone="professional",
            )

            # optimize for each platform
            optimized_content = {}
            for platform in platforms:
                optimized_content[platform] = (
                    social_media_manager.optimize_content_for_platform(
                        content, platform
                    )
                )

            if is_immediate:
                # post now to all platforms
                results = {}
                for platform in platforms:
                    result = await scheduling_tool.post_now(
                        platform=platform, content=optimized_content[platform]
                    )
                    results[platform] = result["result"]

                # format response
                response_parts = ["posts published ✓\n"]
                for platform, result in results.items():
                    if result.get("success"):
                        response_parts.append(f"✓ {platform}: posted")
                    else:
                        response_parts.append(
                            f"✗ {platform}: {result.get('error', 'failed')}"
                        )

                response_parts.append(f"\ncontent:\n{content[:200]}...")
                return "\n".join(response_parts)

            else:
                # schedule for later
                await scheduling_tool.post_to_multiple_platforms(
                    platforms=platforms, content=content, scheduled_at=scheduled_at
                )

                return f"""posts scheduled ✓
platforms: {", ".join(platforms)}
scheduled: {scheduled_at.strftime("%Y-%m-%d %H:%M")}

content preview:
{content[:200]}...

post will be published automatically at scheduled time"""

        except Exception as e:
            return f"error scheduling post: {str(e)}"

    async def _handle_create_campaign(self, text: str, user_info: Dict) -> str:
        try:
            # get cached recipients
            cached = await cache_service.get(f"recipients:{user_info['id']}")
            if not cached:
                return "no recipients cached, please collect emails first"

            recipients = [EmailRecipient(**r) for r in cached]

            # generate email content
            campaign_content = await outreach_tool.generate_campaign_content(
                campaign_type="promotional",
                product_details=text,
                target_audience="existing customers",
            )

            # check if scheduled
            scheduled_at = parse_date_from_text(text)

            # create campaign
            campaign_id = await outreach_tool.create_campaign(
                title=f"campaign_{datetime.now().strftime('%Y%m%d')}",
                recipients=recipients,
                subject=campaign_content["subject"],
                body=campaign_content["body"],
                scheduled_at=scheduled_at,
            )

            status = "scheduled" if scheduled_at else "ready to send"

            return f"""campaign created ✓
campaign id: {campaign_id}
recipients: {len(recipients)}
status: {status}
{f"scheduled: {scheduled_at.strftime('%Y-%m-%d %H:%M')}" if scheduled_at else ""}

subject: {campaign_content["subject"]}

reply "send now" to send immediately or "preview" to see full email"""

        except Exception as e:
            return f"error creating campaign: {str(e)}"

    async def _handle_check_accounts(self) -> str:
        # check which social media accounts are configured
        from services.social_media_manager import social_media_manager

        platforms = ["twitter", "linkedin", "facebook", "instagram"]
        validation = await social_media_manager.validate_platforms(platforms)

        response_parts = ["social media accounts status:\n"]

        for platform, is_valid in validation.items():
            if is_valid:
                info = await social_media_manager.get_platform_info(platform)
                if platform == "twitter" and info:
                    response_parts.append(
                        f"✓ twitter: @{info.get('username', 'unknown')}"
                    )
                elif platform == "linkedin" and info:
                    response_parts.append("✓ linkedin: connected")
                elif platform == "facebook" and info:
                    response_parts.append(
                        f"✓ facebook: {info.get('name', 'page')} ({info.get('fan_count', 0)} followers)"
                    )
                elif platform == "instagram" and info:
                    response_parts.append(
                        f"✓ instagram: @{info.get('username', 'unknown')} ({info.get('followers_count', 0)} followers)"
                    )
                else:
                    response_parts.append(f"✓ {platform}: configured")
            else:
                response_parts.append(f"✗ {platform}: not configured")

        response_parts.append("\nto configure accounts, add credentials to .env file")

        return "\n".join(response_parts)

    async def _get_user_info(self, client, user_id: str) -> Dict:
        try:
            result = await client.users_info(user=user_id)
            return result["user"]
        except Exception:
            return {"id": user_id}

    async def _get_channel_info(self, client, channel_id: str) -> Dict:
        try:
            result = await client.conversations_info(channel=channel_id)
            return result["channel"]
        except Exception:
            return {"id": channel_id, "name": "unknown"}
