from datetime import datetime
from typing import Dict, List, Optional

from core.agent import ai_agent
from models.schemas import (
    DateRangeQuery,
    EmailRecipient,
    OutreachCampaign,
    ScheduledTask,
    SocialMediaPost,
)
from services.database import db_service
from services.email import email_service
from services.scheduler import scheduler_service
from services.shopify import shopify_service


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
        self, campaign_type: str, product_details: str, target_audience: str
    ) -> Dict[str, str]:
        return await ai_agent.generate_email_content(
            campaign_type, product_details, target_audience
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

        return campaign_id

    async def _send_campaign(self, campaign_id: str):
        # get campaign
        campaign = await db_service.get_campaign(campaign_id)
        if not campaign:
            return

        recipients = [EmailRecipient(**r) for r in campaign["recipients"]]

        # send bulk emails
        results = await email_service.send_bulk_emails(
            recipients=recipients,
            subject=campaign["subject"],
            body_template=campaign["body"],
            personalize=True,
        )

        # update campaign status
        await db_service.update_campaign_status(
            campaign_id=campaign_id, status="sent", sent_count=results["sent"]
        )


class SchedulingTool:
    async def post_now(
        self, platform: str, content: str, link: Optional[str] = None
    ) -> Dict:
        # post immediately without scheduling
        from services.social_media_manager import social_media_manager

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
            {"_id": post_id},
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
        from services.social_media_manager import social_media_manager

        post = await db_service.db.social_posts.find_one({"_id": post_id})
        if not post:
            return

        # publish to platform
        result = await social_media_manager.post_to_platform(
            platform=post["platform"], content=post["content"], link=post.get("link")
        )

        # update post status
        status = "published" if result.get("success") else "failed"
        await db_service.db.social_posts.update_one(
            {"_id": post_id},
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
        self, platform: str, topic: str, tone: str = "professional"
    ) -> str:
        prompt = f"""generate {platform} post about: {topic}
tone: {tone}
requirements:
- engaging and concise
- include relevant hashtags
- call to action
- platform-appropriate length"""

        # use ai to generate
        from langchain_core.messages import HumanMessage

        response = await ai_agent.llm.ainvoke([HumanMessage(content=prompt)])

        return response.content

    async def get_scheduled_posts(self, platform: Optional[str] = None) -> List[Dict]:
        return await db_service.get_scheduled_posts(platform)


# tool instances
outreach_tool = OutreachTool()
scheduling_tool = SchedulingTool()
social_media_tool = SocialMediaTool()
