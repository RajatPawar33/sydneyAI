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
