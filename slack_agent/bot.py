import asyncio
import uvicorn
from fastapi import FastAPI
from slack_bolt.adapter.socket_mode.aiohttp import AsyncSocketModeHandler
from slack_bolt.async_app import AsyncApp

from slack_agent.api.test_bot import register_handler
from slack_agent.api.test_bot import router as test_router
from slack_agent.config.settings import settings
from slack_agent.core.handler import SlackHandler
from slack_agent.services.cache import cache_service
from slack_agent.services.database import db_service
from slack_agent.services.scheduler import scheduler_service
from slack_agent.services.webhooks import router as webhook_router
# from fastapi.responses import RedirectResponse
# fastapi app for webhook endpoints
web_app = FastAPI(title="slack-agent webhooks")

web_app.include_router(webhook_router)
web_app.include_router(test_router)
async def startup():
    """Initializes external service connections within the active loop."""
    await db_service.connect()
    await cache_service.connect()
    scheduler_service.start()
    print("✓ services connected")

async def shutdown():
    """Gracefully disconnects services."""
    await db_service.disconnect()
    await cache_service.disconnect()
    scheduler_service.shutdown()
    print("✓ services disconnected")

async def main():
    # 1. Initialize slack app
    app = AsyncApp(
        token=settings.slack_bot_token,
        signing_secret=settings.slack_signing_secret,
    )
    
    # 2. Register handlers
    handler = SlackHandler(app)
    register_handler(handler)

    # 3. Ensure all services connect within THIS specific async loop
    await startup()

    # 4. Prepare the Webhook Server configuration
    # We use a Server instance instead of uvicorn.run to control the loop
    config = uvicorn.Config(app=web_app, host="0.0.0.0", port=8080, log_level="warning")
    server = uvicorn.Server(config)

    # 5. Prepare the Slack Socket Mode handler
    socket_handler = AsyncSocketModeHandler(app, settings.slack_app_token)

    print(f"bot starting with user id: {settings.bot_user_id}...")

    try:
        # Run both the FastAPI server and the Slack Socket handler concurrently
        await asyncio.gather(
            server.serve(),
            socket_handler.start_async()
        )
    except KeyboardInterrupt:
        print("\nshutting down...")
    finally:
        await shutdown()

if __name__ == "__main__":
    try:
        # Standard entry point for the asyncio loop
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nbot stopped")