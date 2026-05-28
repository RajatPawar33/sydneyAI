import asyncio
import httpx
from slack_agent.config.settings import settings

# --- CONFIGURATION ---
SHOPIFY_URL = f"https://{settings.shopify_store_url}/admin/api/2026-01"
SHOPIFY_HEADERS = {
    "X-Shopify-Access-Token": settings.shopify_api_key,
    "Content-Type": "application/json",
}

async def delete_all_shopify_products():
    """Fetches and deletes all products from the Shopify store to clear out data entries."""
    print(f"Connecting to Shopify store: {settings.shopify_store_url}...")
    
    async with httpx.AsyncClient() as client:
        while True:
            # Step 1: Fetch a batch of products (limit 50 for quick processing batches)
            fetch_url = f"{SHOPIFY_URL}/products.json?limit=50&fields=id,title"
            response = await client.get(fetch_url, headers=SHOPIFY_HEADERS)
            
            if response.status_code != 200:
                print(f"❌ Failed to fetch products: {response.text} (Status: {response.status_code})")
                break
                
            products = response.json().get("products", [])
            
            if not products:
                print("\n✨ No products found. Shopify catalog is completely empty and clean!")
                break
                
            print(f"\nFound {len(products)} products to remove. Starting deletion batch...")
            
            # Step 2: Loop through and delete each product in the current batch
            for product in products:
                product_id = product["id"]
                product_title = product["title"]
                
                delete_url = f"{SHOPIFY_URL}/products/{product_id}.json"
                del_response = await client.delete(delete_url, headers=SHOPIFY_HEADERS)
                
                if del_response.status_code == 200:
                    print(f"🗑️ Deleted: {product_title} (ID: {product_id})")
                else:
                    print(f"❌ Failed to delete {product_title}: {del_response.text} (Status: {del_response.status_code})")
            
            # Small break between batches to respect Shopify API rate limits (Leaky Bucket)
            await asyncio.sleep(1)

if __name__ == "__main__":
    try:
        asyncio.run(delete_all_shopify_products())
    except Exception as e:
        print(f"Critical error during catalog wipe: {e}")