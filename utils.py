import re
from typing import Optional, Dict, Any
from datetime import datetime

def format_slack_message(text: str, max_length: int = 3000) -> str:

    if len(text) <= max_length:
        return text
    
    # Truncate and add indicator
    truncated = text[:max_length - 50]
    return f"{truncated}\n\n_[Message truncated due to length]_"


def clean_slack_formatting(text: str) -> str:
 
    # Remove user mentions
    text = re.sub(r"<@[A-Z0-9]+>", "", text)
    
    # Remove channel mentions
    text = re.sub(r"<#[A-Z0-9]+\|([^>]+)>", r"#\1", text)
    
    # Remove link formatting
    text = re.sub(r"<(https?://[^|>]+)\|([^>]+)>", r"\2 (\1)", text)
    text = re.sub(r"<(https?://[^>]+)>", r"\1", text)
    
    # Clean up extra whitespace
    text = " ".join(text.split())
    
    return text.strip()


def parse_marketing_query(text: str) -> Dict[str, Any]:
    text_lower = text.lower()

    # Keyword groups
    strategy_terms = ["strategy", "plan", "planning", "roadmap", "positioning", "growth"]
    analytics_terms = ["analytics", "metrics", "kpi", "data", "performance", "roi", "roas"]
    content_terms = ["content", "blog", "article", "seo", "social media", "post"]
    campaign_terms = ["campaign", "ad", "ads", "advertising", "promotion", "launch"]

    # Detect intent
    if any(term in text_lower for term in strategy_terms):
        query_type = "strategy"
    elif any(term in text_lower for term in analytics_terms):
        query_type = "analytics"
    elif any(term in text_lower for term in content_terms):
        query_type = "content"
    elif any(term in text_lower for term in campaign_terms):
        query_type = "campaign"
    elif any(term in text_lower for term in (
        "marketing", "brand", "customers", "acquisition", "growth"
    )):
        query_type = "general"
    else:
        query_type = "default"   

    # Clean keyword extraction
    words = re.findall(r"\b[a-zA-Z]{5,}\b", text)
    keywords = words[:5]

    return {
        "type": query_type,
        "keywords": keywords,
        "original_text": text,
        "timestamp": datetime.now().isoformat()
    }




def is_bot_message(event: Dict[str, Any]) -> bool:
    return "bot_id" in event or event.get("subtype") == "bot_message"


def format_error_message(error: Exception) -> str:
    
    error_type = type(error).__name__
    
    user_friendly_errors = {
        "TimeoutError": "⏱️ Sorry, that took too long. Please try again.",
        "RateLimitError": "🚦 I'm receiving too many requests. Please wait a moment.",
        "APIError": "🔧 I'm having trouble connecting to my AI brain. Please try again.",
        "ValueError": "❌ I couldn't understand that request. Can you rephrase?",
    }
    
    return user_friendly_errors.get(
        error_type,
        f"😕 Oops! Something went wrong: {str(error)}"
    )



