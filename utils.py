import re
from typing import Optional, Dict, Any
from datetime import datetime


def format_slack_message(text: str, max_length: int = 3000) -> str:
    """
    Format message for Slack, ensuring it fits within length limits
    
    Args:
        text: The message text to format
        max_length: Maximum allowed length
        
    Returns:
        Formatted message text
    """
    if len(text) <= max_length:
        return text
    
    # Truncate and add indicator
    truncated = text[:max_length - 50]
    return f"{truncated}\n\n_[Message truncated due to length]_"


def extract_slack_mentions(text: str) -> list:
    """
    Extract all user mentions from Slack message
    
    Args:
        text: Message text containing mentions
        
    Returns:
        List of user IDs mentioned
    """
    mention_pattern = r"<@([A-Z0-9]+)>"
    return re.findall(mention_pattern, text)


def clean_slack_formatting(text: str) -> str:
    """
    Remove Slack-specific formatting from text
    
    Args:
        text: Text with Slack formatting
        
    Returns:
        Cleaned text
    """
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


def create_slack_blocks(message: str, title: Optional[str] = None) -> list:
    """
    Create Slack Block Kit formatted message
    
    Args:
        message: The main message content
        title: Optional title for the message
        
    Returns:
        List of Slack blocks
    """
    blocks = []
    
    if title:
        blocks.append({
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": title
            }
        })
    
    blocks.append({
        "type": "section",
        "text": {
            "type": "mrkdwn",
            "text": message
        }
    })
    
    return blocks


def parse_marketing_query(text: str) -> Dict[str, Any]:
    """
    Parse a marketing query to extract intent and keywords
    
    Args:
        text: The query text
        
    Returns:
        Dictionary with parsed information
    """
    text_lower = text.lower()
    
    # Detect query type
    query_type = "general"
    
    if any(word in text_lower for word in ["strategy", "plan", "planning", "roadmap"]):
        query_type = "strategy"
    elif any(word in text_lower for word in ["analytics", "metrics", "kpi", "data", "performance"]):
        query_type = "analytics"
    elif any(word in text_lower for word in ["content", "blog", "article", "social media"]):
        query_type = "content"
    elif any(word in text_lower for word in ["campaign", "ad", "advertising", "promotion"]):
        query_type = "campaign"
    
    # Extract potential keywords (simple approach)
    keywords = [word for word in text.split() if len(word) > 4]
    
    return {
        "type": query_type,
        "keywords": keywords[:5],  # Top 5 keywords
        "original_text": text,
        "timestamp": datetime.now().isoformat()
    }


def validate_slack_event(event: Dict[str, Any]) -> bool:
    """
    Validate that a Slack event has required fields
    
    Args:
        event: The Slack event dictionary
        
    Returns:
        True if valid, False otherwise
    """
    required_fields = ["type", "user", "text"]
    return all(field in event for field in required_fields)


def is_bot_message(event: Dict[str, Any]) -> bool:
    """
    Check if a message is from a bot
    
    Args:
        event: The Slack event dictionary
        
    Returns:
        True if from a bot, False otherwise
    """
    return "bot_id" in event or event.get("subtype") == "bot_message"


def format_error_message(error: Exception) -> str:
    """
    Format an error message for user-friendly display
    
    Args:
        error: The exception that occurred
        
    Returns:
        Formatted error message
    """
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


def create_thread_context(messages: list, max_messages: int = 5) -> str:
    """
    Create context from thread messages for the AI
    
    Args:
        messages: List of messages in thread
        max_messages: Maximum number of messages to include
        
    Returns:
        Formatted context string
    """
    if not messages:
        return ""
    
    # Take the most recent messages
    recent_messages = messages[-max_messages:]
    
    context_parts = ["Previous conversation:"]
    for msg in recent_messages:
        user = msg.get("user", "Unknown")
        text = msg.get("text", "")
        context_parts.append(f"- {user}: {text}")
    
    return "\n".join(context_parts)
