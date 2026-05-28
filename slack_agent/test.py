import asyncio
import httpx
from slack_agent.config.settings import settings #

# --- CONFIGURATION ---
# Direct access to Shopify API endpoints as configured in your project
SHOPIFY_URL = f"https://{settings.shopify_store_url}/admin/api/2026-01/products.json" #
SHOPIFY_HEADERS = {
    "X-Shopify-Access-Token": settings.shopify_api_key, #[cite: 1]
    "Content-Type": "application/json",
}

async def seed_shopify_products():
    """Seeds Shopify with a diverse clothing catalog optimized for Sydney's parsing[cite: 1]."""
    print(f"Connecting to: {settings.shopify_store_url}...") #[cite: 1]
    
    catalog = [
        {
            "title": "Urban Nomad Oversized Hoodie",
            "product_type": "Hoodie",
            "tags": "Streetwear, Unisex, Winter 2026, Oversized", #[cite: 1]
            "body_html": (
                "PRODUCT_HIGHLIGHT: Premium 400GSM heavy-weight cotton with a dropped shoulder fit. "
                "TARGET_NICHE: Minimalist Streetwear and Urban Lifestyle. "
                "UNIQUE_SELLING_POINT: Reinforced stitching and a matte fabric finish designed for high-end photography. "
                "BRAND_STORY: Built for the modern traveler who values comfort without sacrificing style."
            ),
            "variants": [{"option1": "Black", "price": "75.00", "sku": "UN-HD-BLK"}]
        },
        {
            "title": "Classic Linen Button-Down",
            "product_type": "Shirt",
            "tags": "Summer 2026, Sustainable, Linen, Men's Fashion", #[cite: 1]
            "body_html": (
                "PRODUCT_HIGHLIGHT: 100% Organic Mediterranean Linen. "
                "TARGET_NICHE: Sustainable Luxury and Coastal Chic. "
                "UNIQUE_SELLING_POINT: Naturally cooling fabric that softens with every wash. "
                "BRAND_STORY: Timeless design meets eco-conscious manufacturing for the summer season."
            ),
            "variants": [{"option1": "White", "price": "55.00", "sku": "LIN-SH-WHT"}]
        },
        {
            "title": "Raw Indigo Slim-Fit Jeans",
            "product_type": "Pants",
            "tags": "Denim, Essential, Menswear, Raw Indigo", #[cite: 1]
            "body_html": (
                "PRODUCT_HIGHLIGHT: 14oz Japanese Selvedge Denim. "
                "TARGET_NICHE: Heritage Workwear and Denim Enthusiasts. "
                "UNIQUE_SELLING_POINT: Unwashed raw indigo that develops unique fade patterns based on the wearer's life. "
                "BRAND_STORY: Authentic craftsmanship designed to age beautifully over years of wear."
            ),
            "variants": [{"option1": "Indigo", "price": "120.00", "sku": "RW-JN-IND"}]
        },
        {
            "title": "Midnight Cargo Joggers",
            "product_type": "Pants",
            "tags": "Techwear, Tactical, Streetwear", #[cite: 1]
            "body_html": (
                "PRODUCT_HIGHLIGHT: Water-resistant nylon-elastane blend for 4-way stretch. "
                "TARGET_NICHE: Techwear and Urban Tactical Aesthetics. "
                "UNIQUE_SELLING_POINT: Hidden zippered utility pockets and adjustable ankle toggles. "
                "BRAND_STORY: Functional performance gear adapted for the city environment."
            ),
            "variants": [{"option1": "Midnight", "price": "95.00", "sku": "MC-JG-MID"}]
        },
        {
            "title": "Essential Pima Cotton Tee",
            "product_type": "T-Shirt",
            "tags": "Basics, Luxury, Sustainable", #[cite: 1]
            "body_html": (
                "PRODUCT_HIGHLIGHT: Grade-A Long-Staple Pima Cotton. "
                "TARGET_NICHE: Premium Basics and Minimalist Wardrobes. "
                "UNIQUE_SELLING_POINT: Ultra-soft, non-pilling fabric with a subtle silk-like sheen. "
                "BRAND_STORY: Elevating the simplest wardrobe staple through superior fabric quality."
            ),
            "variants": [{"option1": "Navy", "price": "35.00", "sku": "ESS-TE-NVY"}]
        },
        {
            "title": "Altitude Puffer Jacket",
            "product_type": "Outerwear",
            "tags": "Winter, Outdoor, Performance", #[cite: 1]
            "body_html": (
                "PRODUCT_HIGHLIGHT: Recycled down insulation with a 700-fill power rating. "
                "TARGET_NICHE: High-Performance Outerwear and Winter Exploration. "
                "UNIQUE_SELLING_POINT: Windproof ripstop shell with an internal heat-trap lining. "
                "BRAND_STORY: Maximum warmth with minimum environmental impact."
            ),
            "variants": [{"option1": "Stone", "price": "180.00", "sku": "ALT-JK-STN"}]
        },
        {
            "title": "Eclipse Boxy Crop Top",
            "product_type": "Top",
            "tags": "Womenswear, Modern, Streetwear", #[cite: 1]
            "body_html": (
                "PRODUCT_HIGHLIGHT: Heavyweight organic jersey knit. "
                "TARGET_NICHE: Modern Feminine Streetwear. "
                "UNIQUE_SELLING_POINT: Structural boxy silhouette that maintains its shape after repeated wear. "
                "BRAND_STORY: Empowering modern style through clean lines and ethical production."
            ),
            "variants": [{"option1": "Cream", "price": "45.00", "sku": "ECL-CP-CRM"}]
        },
        {
    "title": "Apex Performance Polo",
    "product_type": "T-Shirt",
    "tags": "Athleisure, Performance, Summer 2026",
    "body_html": (
        "PRODUCT_HIGHLIGHT: Breathable moisture-wicking polyester blend with 4-way stretch. "
        "TARGET_NICHE: Active Professionals and Athleisure Wear. "
        "UNIQUE_SELLING_POINT: Anti-odor technology with a structured collar that holds shape all day. "
        "BRAND_STORY: Designed for those who move seamlessly between work and workout."
    ),
    "variants": [{"option1": "Charcoal", "price": "50.00", "sku": "AP-PO-CHR"}]
},
{
    "title": "Heritage Flannel Shirt",
    "product_type": "Shirt",
    "tags": "Winter 2026, Casual, Layering, Menswear",
    "body_html": (
        "PRODUCT_HIGHLIGHT: Brushed cotton flannel for superior warmth and softness. "
        "TARGET_NICHE: Casual Layering and Rustic Aesthetic. "
        "UNIQUE_SELLING_POINT: Double-stitched seams with a vintage plaid pattern for timeless appeal. "
        "BRAND_STORY: Inspired by classic outdoor wear, reimagined for everyday comfort."
    ),
    "variants": [{"option1": "Red Plaid", "price": "65.00", "sku": "HF-SH-RDP"}]
},
{
    "title": "Velocity Running Shorts",
    "product_type": "Shorts",
    "tags": "Sportswear, Running, Lightweight, Summer 2026",
    "body_html": (
        "PRODUCT_HIGHLIGHT: Ultra-lightweight mesh fabric with built-in compression lining. "
        "TARGET_NICHE: Runners and Fitness Enthusiasts. "
        "UNIQUE_SELLING_POINT: Reflective detailing and secure zip pocket for essentials. "
        "BRAND_STORY: Engineered for speed, comfort, and endurance during high-performance runs."
    ),
    "variants": [{"option1": "Black", "price": "40.00", "sku": "VR-SH-BLK"}]
}
    ]

    async with httpx.AsyncClient() as client: #[cite: 1]
        for product in catalog:
            payload = {"product": product} #[cite: 1]
            response = await client.post(SHOPIFY_URL, headers=SHOPIFY_HEADERS, json=payload) #[cite: 1]
            
            if response.status_code == 201:
                data = response.json()
                print(f"✅ Created: {data['product']['title']} (ID: {data['product']['id']})")
            else:
                print(f"❌ Failed {product['title']}: {response.text} (Status: {response.status_code})")

async def main():
    try:
        await seed_shopify_products()
        print("\n✨ Shopify Clothing Catalog Seeded Successfully!")
    except Exception as e:
        print(f"Critical error: {e}")

if __name__ == "__main__":
    asyncio.run(main())