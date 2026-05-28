from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from slack_agent.core.handler import SlackHandler
from slack_agent.services.cache import cache_service
from slack_agent.services.database import db_service

router = APIRouter(prefix="/test", tags=["bot-test"])

# lazy ref — set by bot.py after SlackHandler is initialised
_handler: Optional[SlackHandler] = None


def register_handler(handler: SlackHandler):
    global _handler
    _handler = handler


class BotTestRequest(BaseModel):
    message: str = Field(..., min_length=1, description="message to send to the bot")
    user_id: str = Field(default="test_user", description="simulated slack user id")
    username: str = Field(default="Test User", description="simulated slack username")
    channel_id: str = Field(default="test_channel", description="simulated channel id")


class BotTestResponse(BaseModel):
    response: str
    user_id: str
    message: str
    processed_at: str
    rate_limited: bool = False


@router.post("/message", response_model=BotTestResponse)
async def test_bot_message(body: BotTestRequest):
    if not _handler:
        raise HTTPException(status_code=503, detail="slack handler not initialised yet")

    # check rate limit same as real slack flow
    rate_ok = await cache_service.check_rate_limit(body.user_id)
    if not rate_ok:
        return BotTestResponse(
            response="rate limit exceeded — too many messages, wait a moment",
            user_id=body.user_id,
            message=body.message,
            processed_at=datetime.now().isoformat(),
            rate_limited=True,
        )

    # build same user_info / channel_info dicts the slack handler uses internally
    user_info = {
        "user_id": body.user_id,
        "username": body.username,
        "name": body.username,
    }
    channel_info = {
        "channel_id": body.channel_id,
        "channel_name": body.channel_id,
    }

    # pull conversation history from db (same as real flow)
    conv_history = await db_service.get_conversation_history(body.user_id, limit=10)

    # call the exact same method the slack handler calls
    response_text = await _handler._process_command(
        text=body.message,
        user_info=user_info,
        channel_info=channel_info,
        conv_history=conv_history,
    )

    # persist conversation turn so history builds up across test calls
    await db_service.save_conversation(
        user_id=body.user_id,
        message=body.message,
        response=response_text,
    )

    return BotTestResponse(
        response=response_text,
        user_id=body.user_id,
        message=body.message,
        processed_at=datetime.now().isoformat(),
    )


@router.delete("/history/{user_id}")
async def clear_test_history(user_id: str):
    # wipe conversation history for a user so you start a clean test session
    await db_service.db.conversations.delete_many({"user_id": user_id})
    return {"cleared": True, "user_id": user_id}


@router.get("/history/{user_id}")
async def get_test_history(user_id: str, limit: int = 20):
    history = await db_service.get_conversation_history(user_id, limit=limit)
    return {"user_id": user_id, "history": history}
