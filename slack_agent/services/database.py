from datetime import datetime
from typing import Any, Dict, List, Optional

from config.settings import settings
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase


class DatabaseService:
    def __init__(self):
        self.client: Optional[AsyncIOMotorClient] = None
        self.db: Optional[AsyncIOMotorDatabase] = None

    async def connect(self):
        self.client = AsyncIOMotorClient(settings.mongodb_uri)
        self.db = self.client[settings.mongodb_db_name]

    async def disconnect(self):
        if self.client:
            self.client.close()

    # customer operations
    async def get_customers(self, filters: Dict[str, Any]) -> List[Dict]:
        query = {}

        if filters.get("date_range"):
            query["created_at"] = {
                "$gte": filters["date_range"]["start_date"],
                "$lte": filters["date_range"]["end_date"],
            }

        if filters.get("min_orders"):
            query["total_orders"] = {"$gte": filters["min_orders"]}

        if filters.get("tags"):
            query["tags"] = {"$in": filters["tags"]}

        if filters.get("status"):
            query["status"] = filters["status"]

        cursor = self.db.customers.find(query)
        return await cursor.to_list(length=None)

    async def get_customer_emails(self, filters: Dict[str, Any]) -> List[str]:
        customers = await self.get_customers(filters)
        return [c["email"] for c in customers if c.get("email")]

    # outreach campaign operations
    async def save_campaign(self, campaign: Dict[str, Any]) -> str:
        result = await self.db.campaigns.insert_one(campaign)
        return str(result.inserted_id)

    async def get_campaign(self, campaign_id: str) -> Optional[Dict]:
        return await self.db.campaigns.find_one({"id": campaign_id})

    async def update_campaign_status(
        self, campaign_id: str, status: str, sent_count: int = 0
    ):
        await self.db.campaigns.update_one(
            {"id": campaign_id},
            {
                "$set": {
                    "status": status,
                    "sent_count": sent_count,
                    "updated_at": datetime.now(),
                }
            },
        )

    # scheduled tasks operations
    async def save_scheduled_task(self, task: Dict[str, Any]) -> str:
        result = await self.db.scheduled_tasks.insert_one(task)
        return str(result.inserted_id)

    async def get_pending_tasks(self, current_time: datetime) -> List[Dict]:
        cursor = self.db.scheduled_tasks.find(
            {"status": "pending", "scheduled_at": {"$lte": current_time}}
        )
        return await cursor.to_list(length=None)

    async def update_task_status(self, task_id: str, status: str):
        await self.db.scheduled_tasks.update_one(
            {"id": task_id}, {"$set": {"status": status, "updated_at": datetime.now()}}
        )

    # social media posts operations
    async def save_social_post(self, post: Dict[str, Any]) -> str:
        result = await self.db.social_posts.insert_one(post)
        return str(result.inserted_id)

    async def get_scheduled_posts(self, platform: Optional[str] = None) -> List[Dict]:
        query = {"status": "scheduled"}
        if platform:
            query["platform"] = platform

        cursor = self.db.social_posts.find(query).sort("scheduled_at", 1)
        return await cursor.to_list(length=None)

    # conversation history operations
    async def save_conversation(
        self, user_id: str, channel_id: str, message: str, response: str
    ):
        await self.db.conversations.insert_one(
            {
                "user_id": user_id,
                "channel_id": channel_id,
                "message": message,
                "response": response,
                "timestamp": datetime.now(),
            }
        )

    async def get_conversation_history(
        self, user_id: str, limit: int = 10
    ) -> List[Dict]:
        cursor = (
            self.db.conversations.find({"user_id": user_id})
            .sort("timestamp", -1)
            .limit(limit)
        )
        return await cursor.to_list(length=None)


db_service = DatabaseService()
