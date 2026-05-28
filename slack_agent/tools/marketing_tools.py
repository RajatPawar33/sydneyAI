from datetime import datetime
from typing import Dict, List, Optional
from bson import ObjectId
from slack_agent.core.agent import ai_agent
from slack_agent.models.schemas import (
    DateRangeQuery,
    EmailRecipient,
    OutreachCampaign,
    ScheduledTask,
    SocialMediaPost,
)
from slack_agent.services.database import db_service
from slack_agent.services.email import mailgun_client
from slack_agent.services.scheduler import scheduler_service
from slack_agent.services.shopify import shopify_service
import json
from langchain_core.messages import HumanMessage
from slack_agent.core.agent import ai_agent
from slack_agent.services.shopify import shopify_service

class OutreachTool:
    async def collect_customer_emails(
        self,
        source: str = "database",
        date_range: Optional[DateRangeQuery] = None,
        min_orders: int = 0,
        tags: Optional[List[str]] = None,
    ) -> List[EmailRecipient]:
        # collect from database
        if source == "database":
            filters = {
                "date_range": date_range.dict() if date_range else None,
                "min_orders": min_orders,
                "tags": tags,
            }

            customers = await db_service.get_customers(filters)

            return [
                EmailRecipient(
                    email=c["email"],
                    name=c.get("name"),
                    customer_id=c.get("id"),
                    total_orders=c.get("total_orders", 0),
                )
                for c in customers
            ]

        # collect from shopify
        elif source == "shopify":
            since_date = date_range.start_date if date_range else None
            customers = await shopify_service.get_customer_emails(
                since_date=since_date, min_orders=min_orders
            )

            return [
                EmailRecipient(
                    email=c["email"],
                    name=c.get("name"),
                    customer_id=str(c.get("customer_id")),
                    total_orders=c.get("total_orders", 0),
                )
                for c in customers
            ]

        return []

    async def generate_campaign_content(
        self, campaign_type: str, prod_details: str, topic: str
    ) -> Dict[str, str]:
        return await ai_agent.generate_email_content(
            campaign_type, prod_details, topic
        )

    async def create_campaign(
        self,
        title: str,
        recipients: List[EmailRecipient],
        subject: str,
        body: str,
        scheduled_at: Optional[datetime] = None,
    ) -> str:
        campaign = OutreachCampaign(
            title=title,
            recipients=recipients,
            subject=subject,
            body=body,
            scheduled_at=scheduled_at,
        )

        campaign_id = await db_service.save_campaign(campaign.dict())

        # schedule if needed
        if scheduled_at:
            scheduler_service.schedule_task(
                task_id=f"campaign_{campaign_id}",
                func=self._send_campaign,
                run_date=scheduled_at,
                kwargs={"campaign_id": campaign_id},
            )
        else:
            await self._send_campaign(campaign_id)
        return campaign_id

    async def _send_campaign(self, campaign_id: str):
        campaign = await db_service.get_campaign(campaign_id)
        if not campaign:
            print(f"Campaign {campaign_id} not found in database.")
            return

        recipients = [EmailRecipient(**r) for r in campaign["recipients"]]
        raw_body_template = campaign["body"]

        total_sent = 0
        errors = []

        # TEMPORARY DEVELOPMENT CONFIGURATION FOR TESTING
        temporary_destination_url = "https://en.wikipedia.org/wiki/Artificial_intelligence"
        product_title = "Test AI Puffer Jacket"
        product_type = "Outerwear"
        product_tags = ["Testing", "Winter"]
        
        # Replace this string with your active public forwarding address when you run ngrok
        ngrok_base_url = " https://gooey-morphine-swiftly.ngrok-free.dev" 

        for recipient in recipients:
            if not recipient.name or recipient.name == recipient.email.split("@")[0]:
                display_name = "Customer"
            else:
                display_name = recipient.name

            # Build the custom query string targeting your local FastAPI via ngrok
            tracked_link = (
                f"{ngrok_base_url}/track/click"
                f"?email={recipient.email}"
                f"&name={display_name}"
                f"&campaign_id={campaign_id}"
                f"&product_title={product_title}"
                f"&product_type={product_type}"
                f"&redirect_url={temporary_destination_url}"
            )
            for tag in product_tags:
                tracked_link += f"&product_tags={tag}"

            # Swap placeholders inside the raw template string
            personalized_body = raw_body_template.replace("{{name}}", display_name)
            personalized_body = personalized_body.replace("{{product_url}}", tracked_link)

            # Send via SendGrid
            result = await mailgun_client.send_bulk(
                recipients=[recipient],
                subject=campaign["subject"],
                body_template=personalized_body,
                html_template=personalized_body,
                tags=[campaign_id],
            )
            total_sent += result.get("sent", 0)
            if result.get("errors"):
                errors.extend(result["errors"])

        final_status = "sent" if total_sent > 0 else "failed"
        await db_service.update_campaign_status(
            campaign_id=campaign_id, 
            status=final_status, 
            sent_count=total_sent
        )
    # async def _send_campaign(self, campaign_id: str):
    #     campaign = await db_service.get_campaign(campaign_id)
    #     if not campaign:
    #         print(f"Campaign {campaign_id} not found in database.")
    #         return

    #     recipients = [EmailRecipient(**r) for r in campaign["recipients"]]
    #     raw_body_template = campaign["body"]

    #     # Track tracking results
    #     total_sent = 0
    #     errors = []

    #     # Loop through recipients to format personalized fallback salutations
    #     for recipient in recipients:
           
    #         if not recipient.name or recipient.name == recipient.email.split("@")[0]:
    #             display_name = "Customer"
    #         else:
    #             display_name = recipient.name

    #         # Dynamically replace the structured token variable inside the template
    #         personalized_body = raw_body_template.replace("{{name}}", display_name)

    #         # If Mailgun send_bulk tool supports single-recipient parameters, use it.
    #         # Otherwise, execute personalized delivery calls:
    #         result = await mailgun_client.send_bulk(
    #             recipients=[recipient],
    #             subject=campaign["subject"],
    #             body_template=personalized_body,
    #             html_template=personalized_body,
    #             tags=[campaign_id],
    #         )
    #         total_sent += result.get("sent", 0)
    #         if result.get("errors"):
    #             errors.extend(result["errors"])

    #     final_status = "sent" if total_sent > 0 else "failed"

    #     await db_service.update_campaign_status(
    #         campaign_id=campaign_id, 
    #         status=final_status, 
    #         sent_count=total_sent
    #     )
        
    #     print(f"✓ Campaign {campaign_id} processed. Status: {final_status}. Sent: {total_sent}")

class SchedulingTool:
    async def post_now(
        self, platform: str, content: str, link: Optional[str] = None
    ) -> Dict:
        # post immediately without scheduling
        from slack_agent.services.social_media_manager import social_media_manager

        # save to database
        post = SocialMediaPost(
            platform=platform,
            content=content,
            scheduled_at=None,
            media_urls=None,
            tags=None,
        )

        post_id = await db_service.save_social_post(post.dict())

        # publish immediately
        result = await social_media_manager.post_to_platform(
            platform=platform, content=content, link=link
        )

        # update status
        status = "published" if result.get("success") else "failed"
        await db_service.db.social_posts.update_one(
            {"_id": ObjectId(post_id)},
            {
                "$set": {
                    "status": status,
                    "published_at": datetime.now(),
                    "platform_post_id": result.get("post_id"),
                    "error": result.get("error"),
                }
            },
        )

        return {"post_id": post_id, "result": result}

    async def post_to_multiple_platforms(
        self,
        platforms: List[str],
        content: str,
        scheduled_at: Optional[datetime] = None,
        link: Optional[str] = None,
    ) -> Dict[str, str]:
        # post or schedule same content to multiple platforms
        post_ids = {}

        for platform in platforms:
            if scheduled_at:
                # schedule for later
                post_id = await self.schedule_social_post(
                    platform=platform, content=content, scheduled_at=scheduled_at
                )
                post_ids[platform] = post_id
            else:
                # post immediately
                result = await self.post_now(platform, content, link)
                post_ids[platform] = result["post_id"]

        return post_ids

    async def schedule_social_post(
        self,
        platform: str,
        content: str,
        scheduled_at: datetime,
        media_urls: Optional[List[str]] = None,
        tags: Optional[List[str]] = None,
    ) -> str:
        post = SocialMediaPost(
            platform=platform,
            content=content,
            scheduled_at=scheduled_at,
            media_urls=media_urls,
            tags=tags,
        )

        post_id = await db_service.save_social_post(post.dict())

        # schedule posting task
        scheduler_service.schedule_task(
            task_id=f"post_{post_id}",
            func=self._publish_post,
            run_date=scheduled_at,
            kwargs={"post_id": post_id},
        )

        return post_id

    async def schedule_task(
        self,
        description: str,
        scheduled_at: datetime,
        task_type: str,
        created_by: str,
        payload: Dict = None,
    ) -> str:
        task = ScheduledTask(
            task_type=task_type,
            description=description,
            scheduled_at=scheduled_at,
            created_by=created_by,
            payload=payload or {},
        )

        task_id = await db_service.save_scheduled_task(task.dict())

        # schedule task
        scheduler_service.schedule_task(
            task_id=f"task_{task_id}",
            func=self._execute_task,
            run_date=scheduled_at,
            kwargs={"task_id": task_id},
        )

        return task_id

    async def _publish_post(self, post_id: str):
        # get post from database
        from slack_agent.services.social_media_manager import social_media_manager

        post = await db_service.db.social_posts.find_one({"_id": ObjectId(post_id)})
        if not post:
            return

        # publish to platform
        result = await social_media_manager.post_to_platform(
            platform=post["platform"], content=post["content"], link=post.get("link")
        )

        # update post status
        status = "published" if result.get("success") else "failed"
        await db_service.db.social_posts.update_one(
            {"_id": ObjectId(post_id)},
            {
                "$set": {
                    "status": status,
                    "published_at": datetime.now(),
                    "platform_post_id": result.get("post_id"),
                    "error": result.get("error"),
                }
            },
        )

    async def _execute_task(self, task_id: str):
        # placeholder for task execution
        await db_service.update_task_status(task_id, "completed")


class SocialMediaTool:
    async def generate_post_content(
        self, 
        platform: str, 
        topic: str, 
        prod_details: str, 
        tone: str = "professional"
    ) -> str:
    # MODIFIED PROMPT: Added strict output instructions
        prompt = f"""Generate a {platform} post based on these instructions: "{topic}" 
        Use this raw Shopify JSON payload:{prod_details} 

    Tone: {tone}
    Requirements:
    - Extract key details (title, product_type, tags, body_html) automatically from JSON.
    - Engaging, concise, platform-appropriate length.
    - Include relevant hashtags and clear call to action.

    STRICT INSTRUCTION: Return ONLY the raw post text and hashtags ready to publish immediately. No introductory text, markdown code blocks (like ```), labels, explanations, or notes."""
                # use ai to generate
        from langchain_core.messages import HumanMessage
        response = await ai_agent.llm.ainvoke([HumanMessage(content=prompt)])

        # Stripping whitespace to ensure a clean start/end
        return response.content.strip()

    async def get_scheduled_posts(self, platform: Optional[str] = None) -> List[Dict]:
        return await db_service.get_scheduled_posts(platform)



class ProductAmbiguityResolver:
    async def resolve_product(self, user_query: str) -> Optional[Dict]:
        
        # 1. Fetch all products from Shopify catalog
        products = await shopify_service.get_products()
        if not products:
            return None

        # 2. Minimize data payload sent to LLM for token efficiency and precision
        simplified_catalog = [
            {"id": p.get("id"), "title": p.get("title")}
            for p in products
        ]

        # 3. Formulate strict prompt for unambiguous resolution
        prompt = f"""
        You are an intelligent store manager mapping a natural language search query to an exact product entity.
        
        User Search Query: "{user_query}"
        
        Available Catalog Items:
        {json.dumps(simplified_catalog, indent=2)}
        
        Identify the single product from the catalog that best matches the user's intent. 
        If there is no direct or reasonable match, return null.
        
        STRICT OUTPUT INSTRUCTION: 
        Return ONLY a valid JSON object containing the "id" and "title" of the selected product, or null if no match is found.
        Example output format: {{"id": 12345, "title": "Matching Product Name"}}
        DO NOT include any markdown code blocks, labels, introductory phrasing, or trailing notes.
        """

        # 4. Invoke the model
        response = await ai_agent.llm.ainvoke([HumanMessage(content=prompt)])
        
        try:
            matched_data = json.loads(response.content.strip())
        except (ValueError, TypeError):
            return None

        if not matched_data or "id" not in matched_data:
            return None

        # 5. Extract and return the original complete Shopify dictionary matching the ID
        return next((p for p in products if p["id"] == matched_data["id"]), None)


# tool instances
product_resolver = ProductAmbiguityResolver()
outreach_tool = OutreachTool()
scheduling_tool = SchedulingTool()
social_media_tool = SocialMediaTool()
