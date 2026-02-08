from datetime import datetime
from typing import Dict, List, Optional

import httpx
from config.settings import settings


class ShopifyService:
    def __init__(self):
        self.api_key = settings.shopify_api_key
        self.api_secret = settings.shopify_api_secret
        self.store_url = settings.shopify_store_url
        self.base_url = f"https://{self.store_url}/admin/api/2026-01"

    def _get_headers(self) -> Dict[str, str]:
        return {
            "X-Shopify-Access-Token": self.api_key,
            "Content-Type": "application/json",
        }

    async def get_customers(
        self, since_date: Optional[datetime] = None, limit: int = 250
    ) -> List[Dict]:
        async with httpx.AsyncClient() as client:
            params = {"limit": limit}
            if since_date:
                params["created_at_min"] = since_date.isoformat()

            response = await client.get(
                f"{self.base_url}/customers.json",
                headers=self._get_headers(),
                params=params,
            )

            if response.status_code == 200:
                return response.json().get("customers", [])
            return []

    async def get_customer_emails(
        self, since_date: Optional[datetime] = None, min_orders: int = 0
    ) -> List[Dict]:
        customers = await self.get_customers(since_date)

        # filter by order count
        filtered = [
            {
                "email": c.get("email"),
                "name": f"{c.get('first_name', '')} {c.get('last_name', '')}".strip(),
                "customer_id": c.get("id"),
                "total_orders": c.get("orders_count", 0),
                "last_purchase_date": c.get("last_order_date"),
            }
            for c in customers
            if c.get("email") and c.get("orders_count", 0) >= min_orders
        ]

        return filtered

    async def get_products(self, limit: int = 250) -> List[Dict]:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/products.json",
                headers=self._get_headers(),
                params={"limit": limit},
            )

            if response.status_code == 200:
                return response.json().get("products", [])
            return []

    async def get_orders(
        self, since_date: Optional[datetime] = None, status: str = "any"
    ) -> List[Dict]:
        async with httpx.AsyncClient() as client:
            params = {"status": status, "limit": 250}
            if since_date:
                params["created_at_min"] = since_date.isoformat()

            response = await client.get(
                f"{self.base_url}/orders.json",
                headers=self._get_headers(),
                params=params,
            )

            if response.status_code == 200:
                return response.json().get("orders", [])
            return []


shopify_service = ShopifyService()
