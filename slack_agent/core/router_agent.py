import json
from typing import Dict, Literal , Union

from langchain_core.messages import HumanMessage, SystemMessage
# from langchain_community.chat_models import ChatOllama
from langchain_openai import ChatOpenAI
from pydantic import BaseModel
from slack_agent.utils.helpers import extract_email_from_text
from slack_agent.config.settings import settings


client = ChatOpenAI(
    model=settings.openai_model,
    api_key=settings.openai_api_key,
    temperature=0.1,
    model_kwargs={"response_format": {"type": "json_object"}},
)

IntentType = Literal[
    "email_collection",
    "schedule_post",
    "filtered_email_collection",
    "collection_and_campaign",
    "check_accounts",
    "create_campaign",
    "list_products",
    "influencer_campaign",
    "general_chat",
    "poster_generation",
]


class EmailCollectionParams(BaseModel):
    source: Literal["shopify", "database"] = "database"
    date_range: str = ""
    product_tags: list[str] = []   
    product_name: str = ""
    product_type: str = ""         
    total_amount: float = 0.0       

class CollectionAndCampaignParams(BaseModel):
    product_name: str = ""
    source: Literal["shopify", "database"] = "database"
    date_range: str = ""
    product_tags: list[str] = []
    product_type: str = ""
    total_amount: float = 0.0
    status: str = "active"
    recipients_data: list[dict] = []
    # Marketing Copywriting Context
    topic: str = ""

class SchedulePostParams(BaseModel):
    platforms: list[str] = ["twitter"]
    scheduled_time: str = ""
    immediate: bool = False


class CreateCampaignParams(BaseModel):
    topic: str = ""
    scheduled: Union[str, bool] = ""
    emails: list[str] = []
    
class PosterGenerationParams(BaseModel):
    product_name: str = ""
    prompt: str = ""
    aspect_ratio: Literal["square", "landscape", "portrait"] = "portrait"

class LeadsCampaignParams(BaseModel):
    campaign_id: str

class ListProductsParams(BaseModel):
    limit: int = 250

class RoutingResult(BaseModel):
    intent: IntentType
    params: Dict = {}


async def route_intent(message: str, conversation_history: list) -> RoutingResult:
    # Build conversation context
    context_msgs = []
    for turn in conversation_history[-3:]:
        context_msgs.append(f"user: {turn.get('message', '')}")
        context_msgs.append(f"assistant: {turn.get('response', '')[:100]}...")

    context_str = "\n".join(context_msgs) if context_msgs else "no prior context"

    
    system_prompt = f"""you are an intent classifier for a marketing automation bot.

You MUST respond ONLY with valid JSON:
{{
  "intent": "intent_name",
  "params": {{}}
}}

available intents:
1. email_collection - user wants to collect/filter customer emails
    logic: Use this ONLY for bulk filtering from Shopify or the Database. Do NOT use this if a specific email address is provided in the message
   examples: "get emails from last 30 days", "collect customers with 2+ orders"
   params: {{"source": "shopify|database", "min_orders": int, "date_range": "X days"}}

2. list_products - user wants to view a complete list of products from their store
    logic: Use this when the user explicitly requests to see all products, check active items, or print the inventory layout.
    examples: "show me all products", "list all available products", "fetch my shopify product list"
       

3. schedule_post - user wants to either post content immediately or schedule it for a future time on social media. 
   logic: identify if the user intends to publish "now" (immediate=true) or at a specific "future date/time" (immediate=false).
   examples: 
     - "post now on linkedin" 
     - "schedule a linkedin post for next tuesday at 10am" 
     - "generate content and schedule post on linkedin for today at 5pm" 
   params: {{"platforms": ["twitter", "linkedin", "instagram"], "scheduled_time": "natural language or empty", "immediate": true/false}}

4. check_accounts - user wants to verify, list, or check the status of their connected social media accounts.
   logic: identify requests to see which platforms are currently integrated or if those connections are still active.
   examples: 
     - "which accounts do I have connected?"
     - "check my social media status"
     - "verify my platforms"
   params: {{}}
   
5. create_campaign - user wants to generate or send an email campaign to customers that reflects the brand voice.
   logic: identify the core marketing message or topic the user wants to communicate to their customer base.
   - identify the marketing message. 
   - If user says "send now" or similar, set 'scheduled' to false (boolean). 
   - If a specific time is mentioned, set 'scheduled' to that natural language string.
   - If a specific email address (e.g., abc@gmail.com) is in the message, ALWAYS use this intent, NOT email_collection.
   
   examples: 
     - "write a summer sale email in our brand voice and send it"
     - "generate a email about new product and send now to "
     - "send a newsletter to all customers about the holiday discount"
   params: {{"topic": "extracted topic or theme", "scheduled": "natural language or empty"}}

6. influencer_campaign - user wants to find influencers or manage influencer outreach
   examples: "find fashion influencers", "launch influencer campaign for product X"
   params: {{"product_name": "extracted product", "budget": "amount", "platforms": ["youtube", "instagram"]}}

7. filtered_email_collection - user wants to collect/filter customer emails from past transactions
    logic: Use this for bulk filtering customer segments based on registration dates or specific product buying histories.
   examples: 
     - "get emails of customers who bought outerwear garments" -> {{"product_type": "Outerwear"}}
     - "collect customers who bought winter and outdoor gear" -> {{"product_tags": ["Winter", "Outdoor"]}}
     - "find users who spent over 100 dollars on pants" -> {{"product_type": "Pants", "total_amount": 100.0}}
     - "collect emails of customers who bought Midnight Cargo Joggers" -> {{"product_name": "Midnight Cargo Joggers"}}
   params: {{
       "source": "shopify|database", 
       "date_range": "X days or empty", 
       "product_name": "exact product title string if specified or empty",
       "product_tags": ["list", "of", "tags"], 
       "product_type": "string category name", 
       "total_amount": float
   }}

8. collection_and_campaign - User wants to target a segment of customers based on a product's attributes AND generate a promotional email campaign.
   logic: 
   - If the user explicitly mentions a product name to base the target on, extract it into 'product_name'.
   - If the user provides explicit transaction filters directly (like "spent over 100" or "past 30 days"), map them to 'total_amount' or 'date_range' instead of relying on the agent to infer product tags.
   - Extract the email copywriting requirements into 'topic'.

   examples:
     - "My new product is the Altitude Puffer Jacket, collect suitable emails and write a promotional email" 
       -> {{
            "intent": "collection_and_campaign",
            "params": {{"product_name": "Altitude Puffer Jacket", "topic": "promotional email for puffer jacket"}}
          }}
     - "Find customers who spent over 150 on Outerwear and draft a VIP discount newsletter" 
       -> {{
            "intent": "collection_and_campaign",
            "params": {{"product_type": "Outerwear", "total_amount": 150.0, "topic": "VIP discount newsletter"}}
          }}
     - "Look up our Slim-Fit Jeans, gather customers from the last 60 days who bought them, and write a clearance notice"
       -> {{
            "intent": "collection_and_campaign",
            "params": {{"product_name": "Slim-Fit Jeans", "date_range": "60 days", "topic": "clearance notice"}}
          }}

   params: {{
       "product_name": "extracted product name string or empty",
       "source": "database",
       "date_range": "string format or empty",
       "product_tags": ["list", "of", "tags"],
       "product_type": "category string or empty",
       "total_amount": float,
       "status": "active",
       "topic": "full text instruction for writing the copy"
   }}

10. poster_generation - user wants to generate, design, or create a visual poster, advertisement banner, or social media image.
    logic: use this when the user explicitly requests to create or generate visual image content, marketing posters, or promotional graphics. If the user mentions a specific product name to design the poster for, extract it into 'product_name'.
    examples:
      - "generate a promotional poster for our Altitude Puffer Jacket" -> {{"product_name": "Altitude Puffer Jacket", "prompt": "promotional poster for Altitude Puffer Jacket", "aspect_ratio": "square"}}
      - "create an advertising banner with a sleek modern design for Slim-Fit Jeans" -> {{"product_name": "Slim-Fit Jeans", "prompt": "advertising banner with a sleek modern design for Slim-Fit Jeans", "aspect_ratio": "landscape"}}
    params: {{
        "product_name": "extracted product name string or empty", 
        "prompt": "description of the visual layout or theme", 
        "aspect_ratio": "square|landscape|portrait"
    }}

9. general_chat - casual conversation, help requests, or general marketing consultation.
   logic: use this for greetings or when the user asks for strategic advice, industry trends, marketing roadmaps, or brainstorming topics that do not involve immediate execution.
   examples: 
     - "hi, how are you?"
     - "what are the current marketing trends for 2026?"
     - "can you give me a 3-month marketing roadmap for a new brand?"
     - "give me some content ideas for a fitness blog"
   params: {{}}

conversation context:
{context_str}

current message: "{message}"

analyze and classify the intent with extracted parameters."""
    try:
        # 1. Get the AI response
        response = await client.ainvoke(
            [
                SystemMessage(content=system_prompt),
                HumanMessage(content=message),
            ]
        )

        content = response.content.strip()
        try:
            data = json.loads(content)
        except Exception:
            print(" JSON parse failed, raw response:", content)
            return RoutingResult(intent="general_chat", params={})

        # 3. Basic check for the intent key
        intent_name = data.get("intent")
        if not intent_name:
            print("Shifting to general_chat due to missing intent key.")
            return RoutingResult(intent="general_chat", params={})

        
        intent_schemas = {
            "email_collection": EmailCollectionParams,
            "list_products": ListProductsParams,
            "schedule_post": SchedulePostParams,
            "create_campaign": CreateCampaignParams,
            "collection_and_campaign": CollectionAndCampaignParams,  
            "influencer_campaign": InfluencerCampaignParams,
            "poster_generation": PosterGenerationParams,
        }

    
        params = data.get("params", {})
        if intent_name in intent_schemas:
            try:
                # This line runs the validation logic we discussed
                validated_data = intent_schemas[intent_name](**params)
                params = validated_data.model_dump()
            except Exception as ve:
                print(f" Validation failed for {intent_name}: {ve}") 
                # we fall back to general_chat for safety
                print("Shifting to general_chat due to missing intent key.")

                return RoutingResult(intent="general_chat", params={})
        if intent_name == "create_campaign":
            emails_from_text = extract_email_from_text(message)
            # print("Extracted emails from text:", emails_from_text)
            if emails_from_text:
                params["emails"] = list(set(
                    params.get("emails", []) + emails_from_text
                ))
                
        return RoutingResult(intent=intent_name, params=params)

    except Exception as e:
        print(" Routing error:", e)
        return RoutingResult(intent="general_chat", params={})