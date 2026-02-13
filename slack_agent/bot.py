import asyncio
import threading

import uvicorn
from config.settings import settings
from core.handler import SlackHandler
from fastapi import FastAPI
from services.cache import cache_service
from services.database import db_service
from services.scheduler import scheduler_service
from services.webhooks import router as webhook_router
from slack_bolt.adapter.socket_mode.async_handler import AsyncSocketModeHandler
from slack_bolt.async_app import AsyncApp

# fastapi app for webhook endpoints
web_app = FastAPI(title="slack-agent webhooks")
web_app.include_router(webhook_router)


async def startup():
    # connect to services
    await db_service.connect()
    await cache_service.connect()
    scheduler_service.start()
    print("✓ services connected")


async def shutdown():
    # disconnect services
    await db_service.disconnect()
    await cache_service.disconnect()
    scheduler_service.shutdown()
    print("✓ services disconnected")


def run_webhook_server():
    # run fastapi in a separate thread so it doesn't block the slack socket
    uvicorn.run(web_app, host="0.0.0.0", port=8080, log_level="warning")


async def main():
    # initialize slack app
    app = AsyncApp(
        token=settings.slack_bot_token, signing_secret=settings.slack_signing_secret
    )

    # register handlers
    SlackHandler(app)

    # startup
    await startup()

    # start webhook server in background thread
    webhook_thread = threading.Thread(target=run_webhook_server, daemon=True)
    webhook_thread.start()

    print("bot starting...")
    print(f"bot user id: {settings.bot_user_id}")
    print("webhook server: http://0.0.0.0:8080/webhooks/mailgun")

    # start socket mode
    handler = AsyncSocketModeHandler(app, settings.slack_app_token)

    try:
        await handler.start_async()
    except KeyboardInterrupt:
        print("\nshutting down...")
    finally:
        await shutdown()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nbot stopped")
