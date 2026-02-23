from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, EmailStr, Field, field_validator


class QueryType(str, Enum):
    STRATEGY = "strategy"
    ANALYTICS = "analytics"
    CONTENT = "content"
    CAMPAIGN = "campaign"
    OUTREACH = "outreach"
    SCHEDULE = "schedule"
    EMAIL = "email"
    GENERAL = "general"


class UserInfo(BaseModel):
    id: str
    real_name: Optional[str] = None
    email: Optional[str] = None
    team_id: Optional[str] = None


class ChannelInfo(BaseModel):
    id: str
    name: str
    is_private: bool = False


class SlackMessage(BaseModel):
    user: str
    text: str
    channel: str
    ts: str
    thread_ts: Optional[str] = None
    channel_type: Optional[str] = None


class EmailRecipient(BaseModel):
    email: EmailStr
    name: Optional[str] = None
    customer_id: Optional[str] = None
    last_purchase_date: Optional[datetime] = None
    total_orders: Optional[int] = 0


class OutreachCampaign(BaseModel):
    id: str = Field(default_factory=lambda: f"campaign_{datetime.now().timestamp()}")
    title: str
    recipients: List[EmailRecipient]
    subject: str
    body: str
    scheduled_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.now)
    status: str = "draft"
    sent_count: int = 0

    @field_validator("recipients")
    def validate_recipients(cls, v):
        if not v:
            raise ValueError("at least one recipient required")
        return v


class SocialMediaPost(BaseModel):
    platform: str
    content: str
    media_urls: Optional[List[str]] = None
    scheduled_at: Optional[datetime] = None
    tags: Optional[List[str]] = None


class ScheduledTask(BaseModel):
    id: str = Field(default_factory=lambda: f"task_{datetime.now().timestamp()}")
    task_type: str
    description: str
    scheduled_at: datetime
    created_by: str
    status: str = "pending"
    payload: Dict[str, Any] = {}


class AgentResponse(BaseModel):
    content: str
    query_type: QueryType
    metadata: Optional[Dict[str, Any]] = None
    suggested_actions: Optional[List[str]] = None


class DateRangeQuery(BaseModel):
    start_date: datetime
    end_date: datetime

    @field_validator("end_date")
    def validate_date_range(cls, v, values):
        if "start_date" in values and v < values["start_date"]:
            raise ValueError("end_date must be after start_date")
        return v


class CustomerFilter(BaseModel):
    date_range: Optional[DateRangeQuery] = None
    min_orders: Optional[int] = None
    tags: Optional[List[str]] = None
    status: Optional[str] = "active"


# --- influencer models ---


class InfluencerTier(str, Enum):
    NANO = "nano"  # 1k - 10k
    MICRO = "micro"  # 10k - 100k
    MACRO = "macro"  # 100k - 1m
    MEGA = "mega"  # 1m+


class InfluencerStatus(str, Enum):
    DISCOVERED = "discovered"
    CONTACTED = "contacted"
    NEGOTIATING = "negotiating"
    AGREED = "agreed"
    ONBOARDED = "onboarded"
    REJECTED = "rejected"
    NO_RESPONSE = "no_response"


class InfluencerProfile(BaseModel):
    id: str = Field(default_factory=lambda: f"inf_{datetime.now().timestamp()}")
    platform: str  # youtube | instagram
    handle: str
    channel_id: Optional[str] = None  # platform-specific id
    name: str
    bio: Optional[str] = None
    email: Optional[str] = None
    followers: int = 0
    avg_views: Optional[int] = None
    engagement_rate: Optional[float] = None
    niche: Optional[str] = None
    language: Optional[str] = None
    country: Optional[str] = None
    tier: Optional[InfluencerTier] = None
    relevance_score: Optional[float] = None  # 0-1 ai score
    profile_url: Optional[str] = None
    status: InfluencerStatus = InfluencerStatus.DISCOVERED
    tags: List[str] = []
    discovered_at: datetime = Field(default_factory=datetime.now)
    last_contacted_at: Optional[datetime] = None

    @field_validator("tier")
    def set_tier(cls, v, values):
        if v:
            return v
        followers = values.get("followers", 0)
        if followers < 10_000:
            return InfluencerTier.NANO
        elif followers < 100_000:
            return InfluencerTier.MICRO
        elif followers < 1_000_000:
            return InfluencerTier.MACRO
        return InfluencerTier.MEGA


class NegotiationState(BaseModel):
    influencer_id: str
    campaign_id: str
    round: int = 0
    our_budget: float
    offered_budget: Optional[float] = None
    counter_offer: Optional[float] = None
    status: str = "pending"  # pending | accepted | countered | rejected
    messages: List[Dict[str, str]] = []  # {"role": "us|them", "content": "..."}
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)


class InfluencerCampaign(BaseModel):
    id: str = Field(default_factory=lambda: f"icampaign_{datetime.now().timestamp()}")
    title: str
    product_name: str
    product_description: str
    product_attachment_paths: List[str] = []
    target_niche: str
    budget_per_influencer: float
    max_budget: float
    target_platforms: List[str] = ["youtube", "instagram"]
    target_tiers: List[InfluencerTier] = [InfluencerTier.MICRO, InfluencerTier.MACRO]
    min_followers: int = 10_000
    min_engagement_rate: float = 0.02
    status: str = "active"
    influencer_ids: List[str] = []
    created_at: datetime = Field(default_factory=datetime.now)
