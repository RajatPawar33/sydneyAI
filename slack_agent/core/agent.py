import re
import json
from datetime import datetime
from typing import Any, Dict, List

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_community.chat_models import ChatOllama  # Switched to Ollama

from slack_agent.config.settings import settings
from slack_agent.models.schemas import AgentResponse, QueryType


class AIAgent:
    def __init__(self):
        # Initialize Ollama using your Settings class attributes
        self.llm = ChatOllama(
            model=settings.ollama_model,
            base_url=settings.ollama_base_url,
            temperature=settings.ollama_temperature,

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
        specialized_prompts = {
            QueryType.OUTREACH: """
focus: email outreach campaigns
help user:
- collect customer emails from database or shopify
- generate personalized email content
- schedule bulk email sends
""",
            QueryType.SCHEDULE: """
focus: task and post scheduling
confirm exact date, time, and platform.
""",
            QueryType.CONTENT: """
focus: content creation
provide platform-specific formatting and hashtags.
""",
        }

        return base_prompt + specialized_prompts.get(query_type, "")

    async def run(
        self,
        message: str,
        user_info: Dict[str, Any],
        channel_info: Dict[str, Any],
        conversation_history: List[Dict] = None,
    ) -> AgentResponse:
        query_type = self.classify_query(message)
        system_prompt = self.create_system_prompt(query_type, user_info, channel_info)

        messages = [SystemMessage(content=system_prompt)]

        if conversation_history:
            for conv in conversation_history[-5:]:
                messages.append(HumanMessage(content=conv.get("message", "")))
                messages.append(AIMessage(content=conv.get("response", "")))

        messages.append(HumanMessage(content=message))

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
        # Create a specific JSON-only LLM instance for this method
        json_llm = ChatOllama(
            model=settings.ollama_model,
            base_url=settings.ollama_base_url,
            format="json",
            temperature=0.3
        )

        prompt = f"""generate promotional email for:
campaign type: {campaign_type}
product: {product_details}
audience: {target_audience}

Return ONLY a JSON object with:
"subject": (string under 60 chars)
"body": (professional email body)
"cta": (call to action text)"""

        response = await json_llm.ainvoke([HumanMessage(content=prompt)])

        try:
            return json.loads(response.content)
        except (json.JSONDecodeError, TypeError):
            return {
                "subject": f"Special Offer: {campaign_type}",
                "body": response.content,
                "cta": "Click Here",
            }


ai_agent = AIAgent()