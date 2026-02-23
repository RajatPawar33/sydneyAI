from datetime import datetime
from typing import Dict

from slack_bolt.async_app import AsyncApp

from slack_agent.config.settings import settings
from slack_agent.core.agent import ai_agent
from slack_agent.core.router_agent import route_intent
from slack_agent.models.schemas import (
    DateRangeQuery,
    EmailRecipient,
    InfluencerCampaign,
)
from slack_agent.services.cache import cache_service
from slack_agent.services.database import db_service
from slack_agent.tools.influencer_tool import influencer_tool
from slack_agent.tools.marketing_tools import (
    outreach_tool,
    scheduling_tool,
    social_media_tool,
)
from slack_agent.utils.helpers import (
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

            # process command with ai router
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
• influencer discovery & outreach
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
• "find fashion influencers on youtube with 100k+ followers"
• "launch influencer campaign for summer collection budget $500"
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
        # route intent using ai agent instead of keyword matching
        routing = await route_intent(text, user_info, conv_history)
        intent = routing.intent
        params = routing.params

        # dispatch to appropriate handler based on intent
        if intent == "email_collection":
            return await self._handle_email_collection(text, user_info, params)

        elif intent == "schedule_post":
            return await self._handle_schedule_post(text, user_info, params)

        elif intent == "check_accounts":
            return await self._handle_check_accounts()

        elif intent == "create_campaign":
            return await self._handle_create_campaign(text, user_info, params)

        elif intent == "influencer_campaign":
            return await self._handle_influencer_command(text, user_info, params)

        else:  # general_chat
            response = await ai_agent.run(
                message=text,
                user_info=user_info,
                channel_info=channel_info,
                conversation_history=conv_history,
            )
            return response.content

    async def _handle_email_collection(
        self, text: str, user_info: Dict, params: Dict
    ) -> str:
        try:
            # use ai-extracted params or fallback to parsing
            source = params.get(
                "source", "shopify" if "shopify" in text.lower() else "database"
            )
            min_orders = params.get("min_orders", 0)

            # parse date range
            date_range = None
            if "date_range" in params and params["date_range"]:
                import re

                match = re.search(r"(\d+)\s*days?", params["date_range"])
                if match:
                    days = int(match.group(1))
                    from datetime import timedelta

                    end = datetime.now()
                    start = end - timedelta(days=days)
                    date_range = {
                        "start_date": start.isoformat(),
                        "end_date": end.isoformat(),
                    }
            else:
                date_range = parse_date_range_from_text(text)

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

    async def _handle_schedule_post(
        self, text: str, user_info: Dict, params: Dict
    ) -> str:
        try:
            # use ai-extracted platforms or default
            platforms = params.get("platforms", ["twitter"])
            is_immediate = params.get("immediate", False)

            # parse scheduled time if not immediate
            scheduled_at = None
            if not is_immediate:
                if "scheduled_time" in params and params["scheduled_time"]:
                    scheduled_at = parse_date_from_text(params["scheduled_time"])
                else:
                    scheduled_at = parse_date_from_text(text)

                if not scheduled_at:
                    return "couldn't parse schedule time, please specify (e.g., 'tomorrow 3pm') or say 'post now'"

            from services.social_media_manager import social_media_manager

            content = await social_media_tool.generate_post_content(
                platform=platforms[0],
                topic=text,
                tone="professional",
            )

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

    async def _handle_create_campaign(
        self, text: str, user_info: Dict, params: Dict
    ) -> str:
        try:
            # get cached recipients
            cached = await cache_service.get(f"recipients:{user_info['id']}")
            if not cached:
                return "no recipients cached, please collect emails first"

            recipients = [EmailRecipient(**r) for r in cached]

            # use ai-extracted topic if available
            topic = params.get("topic", text)

            campaign_content = await outreach_tool.generate_campaign_content(
                campaign_type="promotional",
                product_details=topic,
                target_audience="existing customers",
            )

            scheduled_at = None
            if params.get("scheduled"):
                scheduled_at = parse_date_from_text(params["scheduled"])
            else:
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

    async def _handle_influencer_command(
        self, text: str, user_info: Dict, params: Dict
    ) -> str:
        try:
            product_name = params.get("product_name", "")
            budget_str = params.get("budget", "500")
            platforms = params.get("platforms", ["youtube", "instagram"])

            # parse budget
            import re

            budget_match = re.search(r"(\d+)", budget_str)
            budget = float(budget_match.group(1)) if budget_match else 500.0

            text_lower = text.lower()

            # launch full discovery + outreach pipeline
            if any(
                w in text_lower
                for w in ["launch", "find", "discover", "start campaign", "search for"]
            ):
                if not product_name:
                    # try to extract from message
                    product_match = re.search(
                        r"(?:for|about|regarding)\s+(.+?)(?:\s+budget|\s+on|\s*$)",
                        text,
                        re.IGNORECASE,
                    )
                    product_name = (
                        product_match.group(1).strip() if product_match else text
                    )

                campaign = InfluencerCampaign(
                    product_name=product_name,
                    product_description=product_name,
                    target_niche=product_name,
                    budget_per_influencer=budget,
                    max_budget=budget * 10,
                    target_platforms=platforms,
                    target_tiers=["micro", "macro"],
                    min_followers=10000,
                    min_engagement_rate=2.0,
                )

                # save campaign to db
                campaign_dict = campaign.dict()
                campaign_dict["id"] = f"icampaign_{datetime.now().timestamp()}"
                campaign_dict["status"] = "running"
                campaign_dict["created_at"] = datetime.now()
                await db_service.db.influencer_campaigns.insert_one(campaign_dict)

                # run full pipeline async
                result = await influencer_tool.run_full_pipeline(campaign)

                discovered = len(result.get("influencers", []))
                scored = len(result.get("scored_influencers", []))
                contacted = result.get("outreach_sent", 0)

                return f"""influencer pipeline launched ✓
campaign id: {campaign_dict["id"]}
product: {product_name}
budget: ${budget} per influencer
platforms: {", ".join(platforms)}

discovery results:
• discovered: {discovered} creators
• scored: {scored} relevant matches
• outreach sent: {contacted}

check dashboard at /influencers for real-time status
you'll get notifications when influencers respond"""

            # check campaign stats
            elif any(
                w in text_lower for w in ["stats", "status", "progress", "how many"]
            ):
                # get latest campaign
                latest = await db_service.db.influencer_campaigns.find_one(
                    {}, sort=[("created_at", -1)]
                )
                if not latest:
                    return "no influencer campaigns found, launch one first with 'find influencers for [product]'"

                campaign_id = latest["id"]
                stats = await influencer_tool.get_pipeline_stats(campaign_id)

                return f"""influencer campaign stats:
campaign: {latest.get("product_name", "unknown")}
status: {latest.get("status", "unknown")}

pipeline breakdown:
• total discovered: {stats.get("total", 0)}
• contacted: {stats.get("contacted", 0)}
• negotiating: {stats.get("negotiating", 0)}
• agreed: {stats.get("agreed", 0)}
• onboarded: {stats.get("onboarded", 0)}
• rejected: {stats.get("rejected", 0)}

response rate: {stats.get("contacted", 0) and round((stats.get("negotiating", 0) + stats.get("agreed", 0)) / stats.get("contacted", 1) * 100, 1)}%"""

            # list influencers by status
            elif any(w in text_lower for w in ["show", "list", "who"]):
                status_filter = None
                if "onboarded" in text_lower:
                    status_filter = "onboarded"
                elif "negotiating" in text_lower:
                    status_filter = "negotiating"
                elif "contacted" in text_lower:
                    status_filter = "contacted"

                query = {"status": status_filter} if status_filter else {}
                cursor = db_service.db.influencers.find(query).limit(10)
                influencers = await cursor.to_list(length=10)

                if not influencers:
                    return f"no influencers found{' with status ' + status_filter if status_filter else ''}"

                lines = [
                    f"influencers{' - ' + status_filter if status_filter else ''}:\n"
                ]
                for inf in influencers:
                    lines.append(
                        f"• {inf['name']} (@{inf['handle']}) - {inf['platform']} - "
                        f"{inf.get('followers', 'unknown')} followers - {inf['status']}"
                    )

                return "\n".join(lines)

            # handle reply/negotiation
            elif any(
                w in text_lower
                for w in ["replied", "responded", "counter", "accepted", "rejected"]
            ):
                # extract influencer handle
                handle_match = re.search(r"@(\w+)", text)
                if not handle_match:
                    return "couldn't find influencer handle, please mention them like '@username replied...'"

                handle = handle_match.group(1)

                # find influencer
                influencer = await db_service.db.influencers.find_one(
                    {"handle": f"@{handle}"}
                )
                if not influencer:
                    return f"influencer @{handle} not found in our database"

                # extract reply content
                reply_match = re.search(
                    r"(?:replied|said|wrote):\s*(.+)$", text, re.IGNORECASE | re.DOTALL
                )
                reply_content = reply_match.group(1).strip() if reply_match else text

                # process negotiation
                result = await influencer_tool.handle_reply(
                    influencer_id=influencer["channel_id"],
                    reply_text=reply_content,
                )

                return f"""reply processed for @{handle} ✓
status: {result.get("status", "unknown")}
action taken: {result.get("action", "none")}

{result.get("message", "negotiation updated")}"""

            else:
                return """influencer commands:
• 'find [niche] influencers on youtube' - discover creators
• 'launch influencer campaign for [product] budget $500' - full pipeline
• 'influencer stats' - check campaign progress
• 'show onboarded influencers' - list by status
• '@username replied: [message]' - process influencer reply

examples:
• "find fashion influencers on instagram with 100k+ followers"
• "launch influencer campaign for summer dress collection budget $300"
• "@fashionista_ria replied: I'd love to collaborate, my rate is $400"
"""

        except Exception as e:
            import traceback

            traceback.print_exc()
            return f"error handling influencer command: {str(e)}"

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
            user = result["user"]
            return {
                "id": user_id,
                "name": user.get("real_name", user.get("name", "unknown")),
                "username": user.get("name", "unknown"),
            }
        except Exception:
            return {"id": user_id, "name": "unknown", "username": "unknown"}

    async def _get_channel_info(self, client, channel_id: str) -> Dict:
        try:
            result = await client.conversations_info(channel=channel_id)
            return result["channel"]
        except Exception:
            return {"id": channel_id, "name": "unknown"}
