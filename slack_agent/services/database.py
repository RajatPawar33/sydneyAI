from datetime import datetime
from typing import Any, Dict, List, Optional
from bson import ObjectId   
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

from slack_agent.config.settings import settings


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

    
    async def get_customers(self, filters: Dict[str, Any]) -> List[Dict]:
        print("\n=== 🔍 DATABASE DEBUG START ===")
        print(f"1. Incoming filters to get_customers: {filters}")
        
        has_order_filters = any(k in filters for k in ["product_tags", "product_type", "product_name", "total_amount"])
        target_customer_ids = None

        if has_order_filters:
            order_query = {}
            or_conditions = []

            # 1. Match by individual product tags
            if filters.get("product_tags"):
                tags = filters["product_tags"]
                if isinstance(tags, str):
                    clean_tags = [t.strip() for t in tags.split(",") if t.strip()]
                elif isinstance(tags, list):
                    clean_tags = []
                    for t in tags:
                        if isinstance(t, str):
                            clean_tags.extend([sub_t.strip() for sub_t in t.split(",") if sub_t.strip()])
                        else:
                            clean_tags.append(t)
                else:
                    clean_tags = tags

                if clean_tags:
                    or_conditions.append({"items.tags": {"$in": clean_tags}})

            # 2. Match strictly by Product Category Type (e.g., "Shirt", "Pants", "Top")
            if filters.get("product_type"):
                or_conditions.append({"items.product_type": filters["product_type"]})

            # 3. Match strictly by Specific Product Name/Title (e.g., "Classic Linen Button-Down")
            if filters.get("product_name"):
                or_conditions.append({"items.title": filters["product_name"]})

            # Combine distinct parameters using standard MongoDB $or mapping
            if or_conditions:
                order_query["$or"] = or_conditions

            # 4. Handle Order Total Amount (Root level filter)
            if filters.get("total_amount"):
                order_query["total_amount"] = {"$gte": float(filters["total_amount"])}

            print(f"2. Generated order_query for MongoDB: {order_query}")

            # Find all unique customer IDs that match these purchase criteria
            cursor = self.db.orders.find(order_query, {"customer_id": 1})
            orders = await cursor.to_list(length=None)
            
            print(f"3. Raw orders found matching query: {orders}")
            
            target_customer_ids = list({order["customer_id"] for order in orders})
            print(f"4. Extracted unique target_customer_ids: {target_customer_ids}")

            # Short-circuit if order requirements match nobody
            if not target_customer_ids:
                print("❌ Stopped at Step 1: No matching customer_ids found in orders collection.")
                print("=== 🔍 DATABASE DEBUG END ===\n")
                return []

        # Step 2: Build the final customer collection query
        customer_query = {}

        if target_customer_ids is not None:
            or_conditions = []
            for c_id in target_customer_ids:
                or_conditions.append({"_id": str(c_id)})
                if isinstance(c_id, str) and len(c_id) == 24 and all(c in "0123456789abcdefABCDEF" for c in c_id):
                    or_conditions.append({"_id": ObjectId(c_id)})
                elif isinstance(c_id, ObjectId):
                    or_conditions.append({"_id": c_id})
            
            if or_conditions:
                customer_query["$or"] = or_conditions
            else:
                print("❌ Stopped at Step 2: Formatted conditions array is empty.")
                print("=== 🔍 DATABASE DEBUG END ===\n")
                return []

        if filters.get("date_range"):
            customer_query["created_at"] = {
                "$gte": filters["date_range"]["start_date"],
                "$lte": filters["date_range"]["end_date"],
            }

        if filters.get("tags"):
            customer_query["tags"] = {"$in": filters["tags"]}

        print(f"5. Generated customer_query for MongoDB: {customer_query}")

        # Step 3: Fetch matching profiles from database
        cursor = self.db.customers.find(customer_query)
        customers = await cursor.to_list(length=None)
        
        print(f"6. Raw customers found matching query: {customers}")
        print("=== 🔍 DATABASE DEBUG END ===\n")
        
        return [
            {
                "name": customer.get("name"),
                "email": customer.get("email")
            }
            for customer in customers if customer.get("email")
        ] 

    async def get_customer_emails(self, filters: Dict[str, Any]) -> List[str]:
        customers = await self.get_customers(filters)
        return [c["email"] for c in customers if c.get("email")]

    # outreach campaign operations
    async def save_campaign(self, campaign: Dict[str, Any]) -> str:
        result = await self.db.campaigns.insert_one(campaign)
        return str(result.inserted_id)

    async def get_campaign(self, campaign_id: str) -> Optional[Dict]:
        campaign = await self.db.campaigns.find_one({"_id": ObjectId(campaign_id)})
        return campaign
    async def update_campaign_status(
        self, campaign_id: str, status: str, sent_count: int = 0
    ):
        await self.db.campaigns.update_one(
            {"_id": campaign_id},
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

    async def get_campaign_stats(self, campaign_id: str) -> dict:
        # aggregate open/click/bounce counters from email_events collection
        pipeline = [
            {"$match": {"campaign_id": campaign_id}},
            {"$group": {"_id": "$event_type", "count": {"$sum": 1}}},
        ]
        cursor = self.db.email_events.aggregate(pipeline)
        rows = await cursor.to_list(length=None)

        stats = {row["_id"]: row["count"] for row in rows}
        delivered = stats.get("delivered", 0)

        return {
            "campaign_id": campaign_id,
            "delivered": delivered,
            "opens": stats.get("opened", 0),
            "clicks": stats.get("clicked", 0),
            "bounces": stats.get("failed", 0),
            "unsubscribes": stats.get("unsubscribed", 0),
            "spam_reports": stats.get("complained", 0),
            "open_rate": round(stats.get("opened", 0) / delivered * 100, 2)
            if delivered
            else 0,
            "click_rate": round(stats.get("clicked", 0) / delivered * 100, 2)
            if delivered
            else 0,
        }

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
    # Add this to your DatabaseService class in services/database.py
    async def add_customer(self, customer_data: Dict[str, Any]) -> str:
        result = await self.db.customers.insert_one(customer_data)
        return str(result.inserted_id)

db_service = DatabaseService()
