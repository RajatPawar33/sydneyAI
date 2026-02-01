"""
Enhanced Agent with Marketing-Specific Features
This is an advanced version you can use to replace agent.py
"""

from typing import TypedDict, Annotated, Sequence, Literal
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, END
from datetime import datetime
import json


class MarketingAgentState(TypedDict):
    """Enhanced state for marketing-focused agent"""
    messages: Annotated[Sequence[BaseMessage], lambda x, y: x + y]
    user_info: dict
    channel_info: dict
    query_type: str  # strategy, analytics, content, campaign, general
    context: dict    # Additional context like campaign data, metrics, etc.


class EnhancedMarketingAgent:
    """
    Advanced marketing agent with specialized capabilities
    """
    
    def __init__(self, model_name: str = "gpt-4-turbo-preview", temperature: float = 0.7):
        self.llm = ChatOpenAI(model=model_name, temperature=temperature)
        self.graph = self._create_graph()
        
        # Marketing-specific knowledge
        self.marketing_frameworks = {
            "strategy": ["SWOT", "Porter's 5 Forces", "Ansoff Matrix", "BCG Matrix"],
            "content": ["AIDA", "Hero-Hub-Hygiene", "Pillar-Cluster"],
            "analytics": ["CAC", "LTV", "ROAS", "CTR", "Conversion Rate"],
        }
        
    def _create_graph(self) -> StateGraph:
        """Create enhanced LangGraph workflow"""
        workflow = StateGraph(MarketingAgentState)
        
        # Define nodes
        workflow.add_node("classify_query", self._classify_query)
        workflow.add_node("enrich_context", self._enrich_context)
        workflow.add_node("generate_response", self._generate_response)
        workflow.add_node("format_output", self._format_output)
        
        # Define edges
        workflow.set_entry_point("classify_query")
        workflow.add_edge("classify_query", "enrich_context")
        workflow.add_edge("enrich_context", "generate_response")
        workflow.add_edge("generate_response", "format_output")
        workflow.add_edge("format_output", END)
        
        return workflow.compile()
    
    def _classify_query(self, state: MarketingAgentState) -> MarketingAgentState:
        """Classify the type of marketing query"""
        messages = state["messages"]
        last_message = messages[-1].content if messages else ""
        
        # Simple classification logic
        query_type = "general"
        text_lower = last_message.lower()
        
        if any(word in text_lower for word in ["strategy", "plan", "planning", "roadmap"]):
            query_type = "strategy"
        elif any(word in text_lower for word in ["analytics", "metrics", "kpi", "data"]):
            query_type = "analytics"
        elif any(word in text_lower for word in ["content", "blog", "social media", "post"]):
            query_type = "content"
        elif any(word in text_lower for word in ["campaign", "ad", "advertising"]):
            query_type = "campaign"
        
        return {
            **state,
            "query_type": query_type
        }
    
    def _enrich_context(self, state: MarketingAgentState) -> MarketingAgentState:
        """Add relevant marketing context based on query type"""
        query_type = state.get("query_type", "general")
        
        # Add relevant frameworks or knowledge
        context = {
            "frameworks": self.marketing_frameworks.get(query_type, []),
            "timestamp": datetime.now().isoformat(),
        }
        
        # Add example metrics for analytics queries
        if query_type == "analytics":
            context["common_metrics"] = [
                "CAC (Customer Acquisition Cost)",
                "LTV (Lifetime Value)",
                "ROAS (Return on Ad Spend)",
                "Conversion Rate",
                "CTR (Click-Through Rate)"
            ]
        
        return {
            **state,
            "context": context
        }
    
    def _generate_response(self, state: MarketingAgentState) -> MarketingAgentState:
        """Generate AI response with enhanced context"""
        messages = state["messages"]
        user_info = state.get("user_info", {})
        channel_info = state.get("channel_info", {})
        query_type = state.get("query_type", "general")
        context = state.get("context", {})
        
        # Create specialized system prompt
        system_prompt = self._create_specialized_prompt(
            user_info, channel_info, query_type, context
        )
        
        # Prepare messages for LLM
        llm_messages = [SystemMessage(content=system_prompt)] + list(messages)
        
        # Generate response
        response = self.llm.invoke(llm_messages)
        
        return {
            **state,
            "messages": [response]
        }
    
    def _format_output(self, state: MarketingAgentState) -> MarketingAgentState:
        """Format the output for Slack"""
        messages = state["messages"]
        
        if not messages:
            return state
        
        last_message = messages[-1]
        
        # Add helpful footer based on query type
        query_type = state.get("query_type", "general")
        footer = self._get_query_footer(query_type)
        
        if isinstance(last_message, AIMessage) and footer:
            enhanced_content = f"{last_message.content}\n\n{footer}"
            last_message.content = enhanced_content
        
        return state
    
    def _create_specialized_prompt(
        self, 
        user_info: dict, 
        channel_info: dict, 
        query_type: str,
        context: dict
    ) -> str:
        """Create a specialized prompt based on query type"""
        user_name = user_info.get("real_name", "User")
        channel_name = channel_info.get("name", "channel")
        
        base_prompt = f"""You are an expert AI Marketing Manager assistant.

Current Context:
- User: {user_name}
- Channel: #{channel_name}
- Query Type: {query_type}
- Date: {datetime.now().strftime('%Y-%m-%d')}
"""
        
        # Add specialized instructions
        specialized_prompts = {
            "strategy": """
Focus Area: Marketing Strategy

Provide strategic insights including:
- Market analysis and positioning
- Competitive landscape
- Growth opportunities
- Long-term planning frameworks

Useful frameworks: SWOT, Porter's 5 Forces, Ansoff Matrix
""",
            "analytics": """
Focus Area: Marketing Analytics

Provide data-driven insights including:
- Key performance indicators (KPIs)
- Metric interpretation
- ROI analysis
- Performance recommendations

Important metrics: CAC, LTV, ROAS, Conversion Rate, CTR
""",
            "content": """
Focus Area: Content Marketing

Provide content strategy guidance including:
- Content planning and calendars
- SEO optimization
- Audience engagement tactics
- Distribution strategies

Useful frameworks: AIDA, Hero-Hub-Hygiene, Topic Clusters
""",
            "campaign": """
Focus Area: Campaign Management

Provide campaign insights including:
- Campaign structure and setup
- Targeting and segmentation
- Budget allocation
- Performance optimization
""",
            "general": """
Provide comprehensive marketing guidance across all areas.
"""
        }
        
        specialized_section = specialized_prompts.get(query_type, specialized_prompts["general"])
        
        guidelines = """
Response Guidelines:
- Be concise but thorough
- Use bullet points for clarity when listing 3+ items
- Provide actionable recommendations
- Include relevant examples when helpful
- Ask clarifying questions if needed
- Keep responses under 500 words for readability
"""
        
        return base_prompt + specialized_section + guidelines
    
    def _get_query_footer(self, query_type: str) -> str:
        """Get a helpful footer based on query type"""
        footers = {
            "strategy": "\n_💡 Need help with implementation? Ask me for specific tactics!_",
            "analytics": "\n_📊 Want to dive deeper into specific metrics? Just ask!_",
            "content": "\n_✍️ Need content ideas or templates? I can help with that!_",
            "campaign": "\n_🚀 Ready to launch? Let me know if you need optimization tips!_",
        }
        
        return footers.get(query_type, "")
    
    def run(
        self, 
        message: str, 
        user_info: dict = None, 
        channel_info: dict = None,
        additional_context: dict = None
    ) -> str:
        """Run the enhanced agent"""
        initial_state = {
            "messages": [HumanMessage(content=message)],
            "user_info": user_info or {},
            "channel_info": channel_info or {},
            "query_type": "general",
            "context": additional_context or {}
        }
        
        try:
            result = self.graph.invoke(initial_state)
            
            # Extract AI response
            ai_messages = [msg for msg in result["messages"] if isinstance(msg, AIMessage)]
            if ai_messages:
                return ai_messages[-1].content
            
            return "I apologize, but I couldn't generate a response. Please try again."
            
        except Exception as e:
            return f"I encountered an error: {str(e)}. Please try rephrasing your question."


# Example usage
if __name__ == "__main__":
    agent = EnhancedMarketingAgent()
    
    # Test different query types
    test_queries = [
        "What's a good Q1 content strategy for B2B SaaS?",
        "How do I calculate ROAS for my campaigns?",
        "Give me some ideas for social media posts about our new product launch",
    ]
    
    for query in test_queries:
        print(f"\nQuery: {query}")
        print("-" * 50)
        response = agent.run(query)
        print(response)
        print("=" * 50)
