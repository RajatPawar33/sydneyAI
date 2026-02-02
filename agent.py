from typing import TypedDict, Annotated, Sequence
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage

from langchain_community.chat_models import ChatOllama


from langgraph.graph import StateGraph, END

import operator


class AgentState(TypedDict):

    messages: Annotated[Sequence[BaseMessage], operator.add]
    user_info: dict
    channel_info: dict
    
class SlackAIAgent:
    def __init__(self, model_name="llama3:8b", temperature=0.7):
        if not model_name:
            raise ValueError("Ollama model name is missing")

        self.llm = ChatOllama(
            model=model_name,       
            temperature=temperature
        )

        self.graph = self._create_graph()



    def _create_graph(self) -> StateGraph:

        workflow = StateGraph(AgentState)
        
        # Define nodes
        workflow.add_node("process_message", self._process_message)
        workflow.add_node("generate_response", self._generate_response)
        
        # Define edges
        workflow.set_entry_point("process_message")
        workflow.add_edge("process_message", "generate_response")
        workflow.add_edge("generate_response", END)
        
        return workflow.compile()
    
    def _process_message(self, state: AgentState) -> AgentState:
        """Process incoming message and add context"""
        messages = state["messages"]
        user_info = state.get("user_info", {})
        channel_info = state.get("channel_info", {})
        
        # Create a system message with context
        system_prompt = self._create_system_prompt(user_info, channel_info)
        
        # Insert system message at the beginning if not already present
        if not messages or not isinstance(messages[0], SystemMessage):
            messages = [SystemMessage(content=system_prompt)] + list(messages)
        
        return {
            "messages": messages,
            "user_info": user_info,
            "channel_info": channel_info
        }
    
    def _generate_response(self, state: AgentState) -> AgentState:
        """Generate AI response using LLM"""
        messages = state["messages"]
        
        # Generate response
        response = self.llm.invoke(messages)
        # response = self.llm.invoke(messages[-1].content)

        
        return {
            "messages": [response],
            "user_info": state["user_info"],
            "channel_info": state["channel_info"]
        }



    def _create_system_prompt(self, user_info: dict, channel_info: dict) -> str:
        """Create a context-aware system prompt"""
        user_name = user_info.get("real_name", "User")
        channel_name = channel_info.get("name", "channel")
        
        return f"""You are a helpful AI Marketing Manager assistant integrated with Slack.
        
Current Context:
- You're chatting with: {user_name}
- Channel: #{channel_name}

Your capabilities:
- Provide marketing strategy advice
- Analyze marketing campaigns
- Suggest content ideas
- Help with marketing analytics
- Answer marketing-related questions

Guidelines:
- Be professional yet friendly
- Provide actionable insights
- Ask clarifying questions when needed
- Keep responses concise for Slack format
- Use bullet points for clarity when listing multiple items

Remember: You're a marketing expert here to help the team succeed!"""
    
    def run(self, message: str, user_info: dict = None, channel_info: dict = None) -> str:
        """Run the agent and get response"""
        initial_state = {
            "messages": [HumanMessage(content=message)],
            "user_info": user_info or {},
            "channel_info": channel_info or {}
        }
        
        result = self.graph.invoke(initial_state)
        
        # Extract the AI's response
        ai_messages = [msg for msg in result["messages"] if isinstance(msg, AIMessage)]
        if ai_messages:
            return ai_messages[-1].content
        
        return "I'm sorry, I couldn't generate a response."
