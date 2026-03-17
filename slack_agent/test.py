from config.settings import settings

print("BOT:", settings.slack_bot_token[:10])
print("APP:", settings.slack_app_token[:10])
print("SECRET:", settings.slack_signing_secret[:5])
