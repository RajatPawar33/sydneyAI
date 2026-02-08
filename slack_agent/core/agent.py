import re
from datetime import datetime
from typing import Any, Dict, List

from config.settings import settings
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from models.schemas import AgentResponse, QueryType


class AIAgent:
    def __init__(self):
        self.llm = ChatOpenAI(
            model=settings.openai_model,
            temperature=settings.openai_temperature,
            max_tokens=settings.openai_max_tokens,
            api_key=settings.openai_api_key,
        )

        self.query_patterns = {
            QueryType.OUTREACH: [
                r"email.*customers?",
                r"outreach.*campaign",
                r"send.*promotional",
                r"collect.*emails?",
                r"generate.*mail",
            ],
            QueryType.SCHEDULE: [
                r"schedule.*(?:post|message|task)",
                r"set.*reminder",
                r"plan.*(?:for|at)",
            ],
            QueryType.STRATEGY: [r"strategy", r"plan(?:ning)?", r"roadmap"],
            QueryType.ANALYTICS: [
                r"analytics?",
                r"metrics?",
                r"kpi",
                r"performance",
                r"data",
            ],
            QueryType.CONTENT: [r"content", r"post", r"social media", r"blog"],
        }

    def classify_query(self, text: str) -> QueryType:
        text_lower = text.lower()

        for query_type, patterns in self.query_patterns.items():
            for pattern in patterns:
                if re.search(pattern, text_lower):
                    return query_type

        return QueryType.GENERAL

    def create_system_prompt(
        self, query_type: QueryType, user_info: Dict, channel_info: Dict
    ) -> str:
        user_name = user_info.get("real_name", "user")
        channel_name = channel_info.get("name", "channel")

        base_prompt = f"""you are an ai marketing assistant for slack
current context:
- user: {user_name}
- channel: #{channel_name}
- date: {datetime.now().strftime("%Y-%m-%d")}

your capabilities:
- marketing strategy and planning
- campaign analysis and optimization
- content generation for social media
- email outreach campaigns
- scheduling posts and tasks
- collecting customer data from shopify
- sending bulk promotional emails

guidelines:
- be concise and actionable
- use bullet points only when listing 3+ items
- ask clarifying questions when needed
- provide specific recommendations
"""

        # add specialized instructions based on query type
        specialized_prompts = {
            QueryType.OUTREACH: """
focus: email outreach campaigns
help user:
- collect customer emails from database or shopify
- generate personalized email content
- schedule bulk email sends
- track campaign performance

when user requests email collection, ask for:
- date range (if needed)
- minimum order count filter
- specific customer segments
""",
            QueryType.SCHEDULE: """
focus: task and post scheduling
help user:
- schedule social media posts
- set reminders for tasks
- create recurring campaigns
- manage content calendar

when scheduling, confirm:
- exact date and time
- platform/channel
- content details
""",
            QueryType.CONTENT: """
focus: content creation
help user:
- generate social media posts
- create campaign copy
- brainstorm content ideas
- optimize for engagement

provide:
- platform-specific formatting
- relevant hashtags
- call-to-action suggestions
""",
        }

        specialized = specialized_prompts.get(query_type, "")

        return base_prompt + specialized

    async def run(
        self,
        message: str,
        user_info: Dict[str, Any],
        channel_info: Dict[str, Any],
        conversation_history: List[Dict] = None,
    ) -> AgentResponse:
        # classify query
        query_type = self.classify_query(message)

        # create system prompt
        system_prompt = self.create_system_prompt(query_type, user_info, channel_info)

        # prepare messages
        messages = [SystemMessage(content=system_prompt)]

        # add conversation history if available
        if conversation_history:
            for conv in conversation_history[-5:]:  # last 5 messages
                messages.append(HumanMessage(content=conv.get("message", "")))
                messages.append(AIMessage(content=conv.get("response", "")))

        # add current message
        messages.append(HumanMessage(content=message))

        # generate response
        response = await self.llm.ainvoke(messages)

        return AgentResponse(
            content=response.content,
            query_type=query_type,
            metadata={
                "user_id": user_info.get("id"),
                "channel_id": channel_info.get("id"),
            },
        )

    async def generate_email_content(
        self, campaign_type: str, product_details: str, target_audience: str
    ) -> Dict[str, str]:
        prompt = f"""generate promotional email for:
campaign type: {campaign_type}
product: {product_details}
audience: {target_audience}

provide:
1. subject line (under 60 chars)
2. email body (professional, persuasive, under 300 words)
3. call to action

format as json"""

        response = await self.llm.ainvoke([HumanMessage(content=prompt)])

        # parse response (implement proper json parsing)
        return {
            "subject": "default subject",
            "body": response.content,
            "cta": "shop now",
        }


ai_agent = AIAgent()
