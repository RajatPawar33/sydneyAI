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
from slack_agent.config.settings import settings
import base64
import json
import logging
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage
from openai import AsyncOpenAI


logger = logging.getLogger(__name__)
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
        product_info: Optional[Dict] = None,  # Added parameter to hold the tracking metrics
    ) -> str:
        campaign = OutreachCampaign(
            title=title,
            recipients=recipients,
            subject=subject,
            body=body,
            scheduled_at=scheduled_at,
        )

        campaign_dict = campaign.dict()
        # Inject the product tracking data directly into the DB document dictionary
        campaign_dict["product_info"] = product_info 

        campaign_id = await db_service.save_campaign(campaign_dict)

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
        product_info = campaign.get("product_info")

        NGROK_BASE_URL = "https://gooey-morphine-swiftly.ngrok-free.dev"
        STORE_BASE_URL = "https://sydney-store-eight.vercel.app"

        total_sent = 0
        errors = []

        for recipient in recipients:
            if not recipient.name or "@" in recipient.name or recipient.name == recipient.email.split("@")[0]:
                display_name = "Customer"
            else:
                display_name = recipient.name
            
            personalized_body = raw_body_template.replace("{{name}}", display_name)
            cta_html = ""

            if product_info and product_info.get("id"):
                prod_id = str(product_info.get("id"))
                prod_title = product_info.get("title", "Product")
                prod_type = product_info.get("product_type", "")

                raw_tags = product_info.get("tags", [])
                if isinstance(raw_tags, str):
                    prod_tags = [t.strip() for t in raw_tags.split(",") if t.strip()]
                else:
                    prod_tags = raw_tags

                query_string = (
                    f"?email={recipient.email}"
                    f"&name={display_name}"
                    f"&campaign_id={campaign_id}"
                    f"&product_title={prod_title}"
                    f"&product_type={prod_type}"
                    f"&product_id={prod_id}"
                )
                for tag in prod_tags:
                    query_string += f"&product_tags={tag}"

                tracking_link = f"{NGROK_BASE_URL}/webhooks/track/click{query_string}"

                cta_html = f"""
                <div style="text-align: center; margin: 30px 0 10px 0;">
                    <a href="{tracking_link}" style="background-color: #4f46e5; color: white; padding: 14px 28px; text-decoration: none; border-radius: 8px; font-weight: bold; display: inline-block; font-family: sans-serif; font-size: 16px;">
                        View {prod_title} on Store &rarr;
                    </a>
                </div>
                """

            email_html_wrapper = f"""
            <div style="background-color: #f9fafb; padding: 40px 20px; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;">
                <div style="max-width: 600px; margin: 0 auto; background-color: #ffffff; padding: 35px; border-radius: 12px; box-shadow: 0 4px 10px rgba(0, 0, 0, 0.04);">
                    <div style="color: #333333; font-size: 16px; line-height: 1.6;">
                        {personalized_body}
                    </div>
                    {cta_html}
                </div>
            </div>
            """

            result = await mailgun_client.send_bulk(
                recipients=[recipient],
                subject=campaign["subject"],
                body_template=personalized_body,
                html_template=email_html_wrapper,
                tags=[campaign_id],
            )
            total_sent += result.get("sent", 0)
            if result.get("errors"):
                errors.extend(result["errors"])

        final_status = "sent" if total_sent > 0 else "failed"
        await db_service.update_campaign_status(campaign_id=campaign_id, status=final_status, sent_count=total_sent)
        print(f"✓ Campaign {campaign_id} processed. Status: {final_status}. Sent: {total_sent}")

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


class PosterTool:
    def __init__(self):
        self.image_client = AsyncOpenAI(api_key=settings.openai_api_key)
        self.llm_client = ChatOpenAI(
            model=settings.openai_model,
            api_key=settings.openai_api_key,
            temperature=0.7,
        )

    async def _optimize_prompt_with_context(self, user_prompt: str, prod_details_json: str) -> str:
        try:
            product_data = json.loads(prod_details_json)
            if not product_data:
                return user_prompt
        except Exception:
            return user_prompt

        
        system_prompt = """
You are an expert ecommerce creative director. The Shopify product data is the PRIMARY source of truth. You MUST design an image prompt for a commercial advertising poster that integrates textual elements.

Requirements:
- The product must remain the central focus, taking up most of the frame.
- Explicitly dictate that the image must be an authentic magazine advertisement layout or promotional poster, NOT a generic lifestyle snapshot.
- TEXT RENDERING: Force the graphic model to overlay text directly into the poster layout using clean typographic structures. 
- Content to overlay as typography elements inside the design:
  1. The exact product title as a prominent, bold display header.
  2. Choose 2 key product feature tags or technical specifications from the context (e.g., "700-Fill Power", "Windproof Ripstop", or "Sustainable Denim") and place them cleanly in small, modern sans-serif callout fonts along the bottom or side margin.
- TEXT STYLE: Specify that all typography must use clean modern fonts, sharp readability, and contrasting text colors that mesh elegantly with the composition background. Avoid generic scrambled lettering.
- Highlight visual materials, texture, craftsmanship, and the product's target luxury niche environment.

Return only the finalized description string to pass straight into the image generator.
"""

        user_message = f"""
Shopify Product Data Context: {json.dumps(product_data, indent=2)}
User's Original Poster Request: "{user_prompt}"

Generate only the optimized, highly-descriptive image prompt string:
"""
        try:
            response = await self.llm_client.ainvoke([
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_message)
            ])
            return response.content.strip()
        except Exception as e:
            logger.error(f"Failed to optimize image prompt: {e}")
            return user_prompt

    async def generate_poster(self, prompt: str, aspect_ratio: str = "portrait", prod_details: str = "{}") -> Optional[bytes]:
        try:
            ratio_mapping = {
                "square": "1024x1024",
                "landscape": "1792x1024",
                "portrait": "1024x1792"
            }
            size_dimension = ratio_mapping.get(aspect_ratio.lower(), "1024x1792")
            optimized_prompt = await self._optimize_prompt_with_context(prompt, prod_details)
            logger.info(f"Generating image using prompt: {optimized_prompt}")
            
            response = await self.image_client.images.generate(
                model="gpt-image-1",
                prompt=optimized_prompt,
                size=size_dimension,
                quality="medium",
                n=1,
            )
            if response.data and len(response.data) > 0:
                image_b64 = response.data[0].b64_json
                return base64.b64decode(image_b64)
        except Exception as e:
            logger.error(f"Image generation failed: {e}")
            return None
        



# tool instances


poster_tool = PosterTool()
product_resolver = ProductAmbiguityResolver()
outreach_tool = OutreachTool()
scheduling_tool = SchedulingTool()
social_media_tool = SocialMediaTool()
