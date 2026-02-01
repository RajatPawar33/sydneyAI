"""
Configuration settings for the Slack AI Bot
"""

# AI Model Configuration
AI_MODEL_NAME = "gpt-4-turbo-preview"
AI_TEMPERATURE = 0.7
AI_MAX_TOKENS = 1000

# Bot Behavior Configuration
ENABLE_THREADING = True  # Always reply in threads for mentions
SHOW_TYPING_INDICATOR = True  # Show "thinking" message

# Response Configuration
MAX_RESPONSE_LENGTH = 3000  # Maximum characters in a response
RESPONSE_TIMEOUT = 30  # Seconds to wait for AI response

# Marketing-specific prompts
MARKETING_FOCUS_AREAS = [
    "Content Marketing",
    "SEO & SEM",
    "Social Media Marketing",
    "Email Marketing",
    "Marketing Analytics",
    "Brand Strategy",
    "Customer Acquisition",
    "Campaign Management"
]

# Custom system prompts for different scenarios
SYSTEM_PROMPTS = {
    "strategy": """You are a strategic marketing advisor. Focus on:
    - Long-term marketing planning
    - Market positioning
    - Competitive analysis
    - Growth strategies""",
    
    "analytics": """You are a marketing analytics expert. Focus on:
    - Data interpretation
    - KPI analysis
    - ROI calculations
    - Performance metrics""",
    
    "content": """You are a content marketing specialist. Focus on:
    - Content strategy
    - SEO optimization
    - Content calendar planning
    - Audience engagement""",
    
    "default": """You are a helpful AI Marketing Manager assistant."""
}
