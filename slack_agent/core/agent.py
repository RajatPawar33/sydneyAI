import re
import json
from datetime import datetime
from typing import Any, Dict, List

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from langchain_openai import ChatOpenAI
from slack_agent.config.settings import settings
from slack_agent.models.schemas import AgentResponse
from openai import AsyncOpenAI
from slack_agent.config.settings import settings

class AIAgent:
    def __init__(self):
        # Initialize Ollama using your Settings class attributes
        self.llm = ChatOpenAI(
            model=settings.openai_model,
            api_key=settings.openai_api_key,
            temperature=settings.ollama_temperature,
        )

       

    def create_system_prompt(
        self, user_info: Dict, channel_info: Dict
    ) -> str:
        user_name = user_info.get("real_name", "user")
        channel_name = channel_info.get("name", "channel")

        # Return a single, clean, consistent conversational prompt for all general chats
        return f"""you are an ai marketing assistant for slack
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
       
  

    from slack_agent.services.search import search_service
    async def run(
        self,
        message: str,
        user_info: Dict[str, Any],
        channel_info: Dict[str, Any],
        conversation_history: List[Dict] = None,
        query_type: str = "general", 
    ) -> AgentResponse:
        system_prompt = self.create_system_prompt(user_info, channel_info)
        messages = [SystemMessage(content=system_prompt)]

        if conversation_history:
            for conv in conversation_history[-5:]:
                messages.append(HumanMessage(content=conv.get("message", "")))
                messages.append(AIMessage(content=conv.get("response", "")))

        if query_type == "general_chat":
            web_insights = await self.search_service.fetch_web_context(query=message)
            if web_insights:
                search_injection = (
                    f"ADDITIONAL REAL-TIME CONTEXT FROM THE WEB:\n"
                    f"Use this fresh information if applicable to accurately answer the user:\n"
                    f"{web_insights}"
                )
                messages.append(SystemMessage(content=search_injection))

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
        self, campaign_type: str, prod_details: str, topic: str
    ) -> Dict[str, str]:
        # Create a specific JSON-only LLM instance for this method
        json_llm = ChatOpenAI(
            model=settings.openai_model,
            api_key=settings.openai_api_key,
            model_kwargs={"response_format": {"type": "json_object"}},
            temperature=0.3
        )

       # Inside slack_agent/core/agent.py -> generate_email_content

     # Inside slack_agent/core/agent.py -> generate_email_content

        prompt = f"""You are a luxury conversion-focused email marketer. 
        Generate a promotional email matching these instructions: "{topic}" 
        Using this raw Shopify JSON product data: {prod_details} 
        Campaign Type: {campaign_type}

        Layout Requirements:
        - STRUCTURE: Divide the email body copy into 3 distinct sections: 
        1. An attention-grabbing hook paragraph.
        2. A benefit-driven feature body paragraph.
        3. A short, urgent closing call-to-action transition sentence.
        - FORMAT: Wrap each section in semantic HTML `<p style="line-height: 1.6; margin-bottom: 16px; font-family: sans-serif; color: #333333; font-size: 16px;"></p>` paragraph tags. Do NOT output a single wall of text.
        - SALUTATION REQUIREMENT: Start the first paragraph exactly with "Hi {{name}}," as a placeholder variable.

        STRICT INSTRUCTION: Return ONLY a valid JSON object matching the schema below. Do not include markdown code blocks (like ```json), explanations, or notes.

        Output Format:
        {{
        "subject": "Clear, high-open-rate subject line under 60 characters",
        "body": "<p style='...'>Hi {{name}},\\n\\n[Hook content Here]</p><p style='...'>[Benefits here]</p><p style='...'>[Urgency wrapper text]</p>",
        "cta": "Urgent, benefit-driven Call-To-Action text"
        }}"""

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