import logging
from tavily import AsyncTavilyClient
from slack_agent.config.settings import settings

logger = logging.getLogger(__name__)

class SearchService:
    def __init__(self):
        # Initializes the client if the key is provided
        self.client = AsyncTavilyClient(api_key=settings.tavily_api_key) if settings.tavily_api_key else None

    async def fetch_web_context(self, query: str) -> str:
        if not self.client:
            logger.warning("Tavily API key is missing. Skipping real-time web context search.")
            return ""
        
        try:
            # We use 'smart' depth for optimization and cap at 5 results to control token sizes
            response = await self.client.search(query=query, search_depth="smart", max_results=5)
            
            results = response.get("results", [])
            if not results:
                return "No matching real-time data found on the web."
                
            # Build clean contextual strings for the LangChain prompt injection
            context_blocks = [
                f"Source URL: {item['url']}\nInformation: {item['content']}"
                for item in results
            ]
            return "\n\n".join(context_blocks)
            
        except Exception as e:
            logger.error(f"Failed to query Tavily API: {e}")
            return f"Error retrieving real-time information: {str(e)}"

search_service = SearchService() 