import asyncio
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
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

# FastAPI app for webhook endpoints (Handles Mailgun, SendGrid, and Twilio WhatsApp)
web_app = FastAPI(title="slack-agent webhooks")


origins = [
    "http://localhost:3000",
    "http://localhost:8080",
    "https://sydney-store-eight.vercel.app",  # Your deployed Vercel storefront URL
]

web_app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],  # Allows POST, GET, OPTIONS, etc.
    allow_headers=["*"],  # Allows Content-Type and other frontend headers
)
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

    # 3. Bridge Coupling: Expose the handler instantiation to the FastAPI application state.
    # This allows the WhatsApp webhook route to access the core AI processing pipelines.
    web_app.state.slack_handler = handler

    # 4. Ensure all services connect within THIS specific async loop
    await startup()

    # 5. Prepare the Webhook Server configuration
    # We use a Server instance instead of uvicorn.run to control the loop execution manually
    config = uvicorn.Config(app=web_app, host="0.0.0.0", port=8080, log_level="warning")
    server = uvicorn.Server(config)

    # 6. Prepare the Slack Socket Mode handler
    socket_handler = AsyncSocketModeHandler(app, settings.slack_app_token)

    print(f"bot starting with user id: {settings.bot_user_id}...")

    try:
        # Run both the FastAPI server (WhatsApp & Webhooks) and the Slack Socket handler concurrently
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