
from datetime import datetime
from typing import TypedDict, Annotated, Sequence
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage
from langchain_community.chat_models import ChatOllama
from langgraph.graph import StateGraph, END
from utils import parse_marketing_query
from config import SYSTEM_PROMPTS


class MarketingAgentState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], lambda x, y: x + y]
    user_info: dict
    channel_info: dict
    query_type: str
    context: dict

class EnhancedMarketingAgent:
  
    def __init__(self, model_name="llama3:8b", temperature=0.7 ):
        self.llm = ChatOllama(
            model=model_name,
            temperature=temperature
        )
        self.graph = self._create_graph()


    def _create_graph(self) -> StateGraph:
        workflow = StateGraph(MarketingAgentState)

        workflow.add_node("generate_response", self._generate_response)
        workflow.set_entry_point("generate_response")
        workflow.add_edge("generate_response", END)

        return workflow.compile()

    def _generate_response(self,state: MarketingAgentState ) -> MarketingAgentState:

        messages = state["messages"]
        user_info = state.get("user_info", {})
        channel_info = state.get("channel_info", {})
        query_type = state.get("query_type", "default")
        context = state.get("context", {})

        user_name = user_info.get("real_name", "User")
        channel_name = channel_info.get("name", "channel")

        # Get base prompt from config
        base_prompt = SYSTEM_PROMPTS.get(
            query_type,
            SYSTEM_PROMPTS["default"]
        )

        # Build final system prompt
        system_prompt = f"""
            {base_prompt}

            Context:
            - User: {user_name}
            - Channel: #{channel_name}
            - Detected Intent: {query_type}
            - Keywords: {", ".join(context.get("keywords", []))}
            - Date: {datetime.now().strftime("%Y-%m-%d")}

            Response Guidelines:
            - Be concise and actionable
            - Use bullet points for clarity
            - Provide practical marketing advice
            - Ask clarifying questions if information is missing
            """

        llm_messages = [
            SystemMessage(content=system_prompt),
            *messages
        ]

        response = self.llm.invoke(llm_messages)

        return {
            **state,
            "messages": [response]
        }


    def run(self, message: str, user_info: dict | None = None, channel_info: dict | None = None ) -> str:

        parsed = parse_marketing_query(message)

        initial_state: MarketingAgentState = {
            "messages": [HumanMessage(content=message)],
            "user_info": user_info or {},
            "channel_info": channel_info or {},
            "query_type": parsed.get("type", "default"),
            "context": parsed
        }

        try:
            result = self.graph.invoke(initial_state)

            ai_messages = [
                msg for msg in result["messages"]
                if isinstance(msg, AIMessage)
            ]

            if ai_messages:
                return ai_messages[-1].content

            return "I couldn't generate a response. Please try again."

        except Exception as e:
            return (
                "I ran into an error while processing your request. "
                "Please try rephrasing your question."
            )
