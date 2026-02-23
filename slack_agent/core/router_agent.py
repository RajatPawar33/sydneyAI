from typing import Dict, Literal

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from pydantic import BaseModel

from slack_agent.config.settings import settings

client = ChatOpenAI(
    model=settings.openai_model,
    temperature=0.1,
    max_tokens=1000,
    api_key=settings.openai_api_key,
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
    date_range: str = ""  # e.g. "30 days", "last week"


class SchedulePostParams(BaseModel):
    platforms: list[str] = ["twitter"]
    scheduled_time: str = ""  # natural language time
    immediate: bool = False


class CreateCampaignParams(BaseModel):
    topic: str = ""
    scheduled: str = ""  # natural language time or empty


class InfluencerCampaignParams(BaseModel):
    product_name: str = ""
    budget: str = "500"
    platforms: list[str] = ["youtube", "instagram"]


class RoutingResult(BaseModel):
    intent: IntentType
    params: Dict = {}


async def route_intent(message: str, conversation_history: list) -> RoutingResult:
    # build conversation context
    context_msgs = []
    for turn in conversation_history[-3:]:
        context_msgs.append(f"user: {turn.get('message', '')}")
        context_msgs.append(f"assistant: {turn.get('response', '')[:100]}...")

    context_str = "\n".join(context_msgs) if context_msgs else "no prior context"

    system_prompt = f"""you are an intent classifier for a marketing automation bot.

available intents:
1. email_collection - user wants to collect/filter customer emails
   examples: "get emails from last 30 days", "collect customers with 2+ orders"
   params: {{"source": "shopify|database", "min_orders": int, "date_range": "X days"}}
   
2. schedule_post - user wants to schedule or post content to social media
   examples: "post to twitter tomorrow", "schedule instagram post for friday 3pm"
   params: {{"platforms": ["twitter", "linkedin"], "scheduled_time": "natural language", "immediate": true/false}}
   
3. check_accounts - user wants to verify social media account status
   examples: "check my accounts", "verify platforms"
   params: {{}}
   
4. create_campaign - user wants to create/send an email campaign
   examples: "send campaign about summer sale", "create promotional email"
   params: {{"topic": "extracted topic", "scheduled": "time or empty"}}
   
5. influencer_campaign - user wants to find influencers or manage influencer outreach
   examples: "find fashion influencers", "launch influencer campaign for product X"
   params: {{"product_name": "extracted product", "budget": "amount", "platforms": ["youtube", "instagram"]}}
   
6. general_chat - casual conversation, questions, help requests

conversation context:
{context_str}

current message: "{message}"

analyze and classify the intent with extracted parameters."""

    # use structured output with openai
    structured_llm = client.with_structured_output(RoutingResult)

    result = await structured_llm.ainvoke(
        [SystemMessage(content=system_prompt), HumanMessage(content=message)]
    )

    return result
