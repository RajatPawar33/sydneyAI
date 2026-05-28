import asyncio
from datetime import datetime
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorClient
from slack_agent.config.settings import settings


async def seed_orders():
    # Connect to MongoDB using your existing settings configuration
    client = AsyncIOMotorClient(settings.mongodb_uri)
    db = client[settings.mongodb_db_name]

    print(f"Connecting to database: {settings.mongodb_db_name}...")

    # Order history perfectly mapped to your custom customer ObjectIds
    orders_data = [
        # --- Orders for Rajat Pawar (customer_id: 69f87260098fe85b8bf4161c) ---
        {
            "_id": ObjectId("69f8727a7701c4f2ee1a2991"),
            "customer_id": "69f87260098fe85b8bf4161c",
            "order_date": datetime.fromisoformat("2025-04-10T11:20:00.000+00:00"),
            "total_amount": 110.00,
            "status": "completed",
            "items": [
                {
                    "product_id": "8058039402614",
                    "title": "Classic Linen Button-Down",
                    "product_type": "Shirt",
                    "quantity": 2,
                    "price_at_purchase": 55.00,
                    "tags": ["Summer 2026", "Sustainable", "Linen", "Men's Fashion"]
                }
            ]
        },

        # --- Orders for RP (customer_id: 69f8726e7701c4f2ee1a28b5) ---
        {
            "_id": ObjectId("69f8727a7701c4f2ee1a2992"),
            "customer_id": "69f8726e7701c4f2ee1a28b5",
            "order_date": datetime.fromisoformat("2026-05-03T09:15:00.000+00:00"),
            "total_amount": 170.00,
            "status": "completed",
            "items": [
                {
                    "product_id": "8058039304310",
                    "title": "Urban Nomad Oversized Hoodie",
                    "product_type": "Hoodie",
                    "quantity": 1,
                    "price_at_purchase": 75.00,
                    "tags": ["Streetwear", "Unisex", "Winter 2026", "Oversized"]
                },
                {
                    "product_id": "8058039533686",
                    "title": "Midnight Cargo Joggers",
                    "product_type": "Pants",
                    "quantity": 1,
                    "price_at_purchase": 95.00,
                    "tags": ["Techwear", "Tactical", "Streetwear"]
                }
            ]
        },

        # --- Orders for Sachin Phapale (customer_id: 69f8726e7701c4f2ee1a28b6) ---
        {
            "_id": ObjectId("69f8727a7701c4f2ee1a29a1"),
            "customer_id": "69f8726e7701c4f2ee1a28b6",
            "order_date": datetime.fromisoformat("2026-01-15T10:30:00.000+00:00"),
            "total_amount": 255.00,
            "status": "completed",
            "items": [
                {
                    "product_id": "8058039631990",
                    "title": "Altitude Puffer Jacket",
                    "product_type": "Outerwear",
                    "quantity": 1,
                    "price_at_purchase": 180.00,
                    "tags": ["Winter", "Outdoor", "Performance"]
                },
                {
                    "product_id": "8058039304310",
                    "title": "Urban Nomad Oversized Hoodie",
                    "product_type": "Hoodie",
                    "quantity": 1,
                    "price_at_purchase": 75.00,
                    "tags": ["Streetwear", "Unisex", "Winter 2026", "Oversized"]
                }
            ]
        },
        {
            "_id": ObjectId("69f8727a7701c4f2ee1a29a2"),
            "customer_id": "69f8726e7701c4f2ee1a28b6",
            "order_date": datetime.fromisoformat("2026-02-20T14:15:00.000+00:00"),
            "total_amount": 95.00,
            "status": "completed",
            "items": [
                {
                    "product_id": "8058039533686",
                    "title": "Midnight Cargo Joggers",
                    "product_type": "Pants",
                    "quantity": 1,
                    "price_at_purchase": 95.00,
                    "tags": ["Techwear", "Tactical", "Streetwear"]
                }
            ]
        },

        # --- Orders for Siddhedh Patil (customer_id: 69f8726e7701c4f2ee1a28b8) ---
        {
            "_id": ObjectId("69f8727a7701c4f2ee1a29a3"),
            "customer_id": "69f8726e7701c4f2ee1a28b8",
            "order_date": datetime.fromisoformat("2025-11-05T09:00:00.000+00:00"),
            "total_amount": 120.00,
            "status": "completed",
            "items": [
                {
                    "product_id": "8058039468150",
                    "title": "Raw Indigo Slim-Fit Jeans",
                    "product_type": "Pants",
                    "quantity": 1,
                    "price_at_purchase": 120.00,
                    "tags": ["Denim", "Essential", "Menswear", "Raw Indigo"]
                }
            ]
        },
        {
            "_id": ObjectId("69f8727a7701c4f2ee1a29a4"),
            "customer_id": "69f8726e7701c4f2ee1a28b8",
            "order_date": datetime.fromisoformat("2026-04-12T18:22:00.000+00:00"),
            "total_amount": 215.00,
            "status": "completed",
            "items": [
                {
                    "product_id": "8058039631990",
                    "title": "Altitude Puffer Jacket",
                    "product_type": "Outerwear",
                    "quantity": 1,
                    "price_at_purchase": 180.00,
                    "tags": ["Winter", "Outdoor", "Performance"]
                },
                {
                    "product_id": "8058039566454",
                    "title": "Essential Pima Cotton Tee",
                    "product_type": "T-Shirt",
                    "quantity": 1,
                    "price_at_purchase": 35.00,
                    "tags": ["Basics", "Luxury", "Sustainable"]
                }
            ]
        }
    ]

    print("Inserting data directly into the orders collection...")
    
    for order in orders_data:
        try:
            # Using upsert linked by the order's unique ObjectId 
            await db.orders.update_one(
                {"_id": order["_id"]},
                {"$set": order},
                upsert=True
            )
            print(f"Successfully added/updated order: {order['_id']} for customer ID: {order['customer_id']}")
        except Exception as e:
            print(f"Failed to insert order {order['_id']}: {e}")

    client.close()
    print("\n✨ Relational Orders collection seeding completed successfully!")

if __name__ == "__main__":
    asyncio.run(seed_orders())