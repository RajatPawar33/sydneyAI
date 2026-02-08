import asyncio

from config.settings import settings
from core.handler import SlackHandler
from services.cache import cache_service
from services.database import db_service
from services.scheduler import scheduler_service
from slack_bolt.adapter.socket_mode.async_handler import AsyncSocketModeHandler
from slack_bolt.async_app import AsyncApp


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


async def main():
    # initialize slack app
    app = AsyncApp(
        token=settings.slack_bot_token, signing_secret=settings.slack_signing_secret
    )

    # register handlers
    SlackHandler(app)

    # startup
    await startup()

    print("bot starting...")
    print(f"bot user id: {settings.bot_user_id}")

    # start socket mode
    handler = AsyncSocketModeHandler(app, settings.slack_app_token)

    try:
        await handler.start_async()
    except KeyboardInterrupt:
        print("\n shutting down...")
    finally:
        await shutdown()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nbot stopped")
