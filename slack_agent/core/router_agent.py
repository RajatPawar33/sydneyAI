import json
from typing import Dict, Literal , Union

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_community.chat_models import ChatOllama
from pydantic import BaseModel
from slack_agent.utils.helpers import extract_email_from_text
from slack_agent.config.settings import settings


client = ChatOllama(
    model="llama3:8b",
    base_url=settings.ollama_base_url,
    temperature=0.1,
    format="json",
)

IntentType = Literal[
    "email_collection",
    "schedule_post",
    "check_accounts",
    "create_campaign",
    "influencer_campaign",
    "general_chat",
]


class EmailCollectionParams(BaseModel):
    source: Literal["shopify", "database"] = "database"
    min_orders: int = 0
    date_range: str = ""


class SchedulePostParams(BaseModel):
    platforms: list[str] = ["twitter"]
    scheduled_time: str = ""
    immediate: bool = False


class CreateCampaignParams(BaseModel):
    topic: str = ""
    scheduled: Union[str, bool] = ""
    emails: list[str] = []

class InfluencerCampaignParams(BaseModel):
    product_name: str = ""
    budget: str = "500"
    platforms: list[str] = ["youtube", "instagram"]


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
   
2. 2. schedule_post - user wants to either post content immediately or schedule it for a future time on social media. 
   logic: identify if the user intends to publish "now" (immediate=true) or at a specific "future date/time" (immediate=false).
   examples: 
     - "post now on linkedin" 
     - "schedule a linkedin post for next tuesday at 10am" 
     - "generate content and schedule post on linkedin for today at 5pm" 
   params: {{"platforms": ["twitter", "linkedin", "instagram"], "scheduled_time": "natural language or empty", "immediate": true/false}}

3. check_accounts - user wants to verify, list, or check the status of their connected social media accounts.
   logic: identify requests to see which platforms are currently integrated or if those connections are still active.
   examples: 
     - "which accounts do I have connected?"
     - "check my social media status"
     - "verify my platforms"
   params: {{}}
   
4. create_campaign - user wants to generate or send an email campaign to customers that reflects the brand voice.
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

5. influencer_campaign - user wants to find influencers or manage influencer outreach
   examples: "find fashion influencers", "launch influencer campaign for product X"
   params: {{"product_name": "extracted product", "budget": "amount", "platforms": ["youtube", "instagram"]}}
   
6. 6. general_chat - casual conversation, help requests, or general marketing consultation.
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
            "schedule_post": SchedulePostParams,
            "create_campaign": CreateCampaignParams,
            "influencer_campaign": InfluencerCampaignParams,
            # general_chat and check_accounts don't need extra params validation
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
            print("Extracted emails from text:", emails_from_text)
            if emails_from_text:
                params["emails"] = list(set(
                    params.get("emails", []) + emails_from_text
                ))
                
        return RoutingResult(intent=intent_name, params=params)

    except Exception as e:
        print(" Routing error:", e)
        return RoutingResult(intent="general_chat", params={})