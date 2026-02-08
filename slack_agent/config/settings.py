from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", case_sensitive=False, extra="ignore"
    )

    # slack credentials
    slack_bot_token: str
    slack_app_token: str
    slack_signing_secret: str
    bot_user_id: str

    # openai credentials
    openai_api_key: str
    openai_model: str = "gpt-4o-mini"
    openai_temperature: float = 0.7
    openai_max_tokens: int = 1000

    # redis config
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_db: int = 0
    redis_password: Optional[str] = None

    # mongodb config
    mongodb_uri: str = "mongodb://localhost:27017"
    mongodb_db_name: str = "slack_agent"

    # email config
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_username: Optional[str] = None
    smtp_password: Optional[str] = None
    smtp_from_email: Optional[str] = None

    # shopify config
    shopify_api_key: Optional[str] = None
    shopify_api_secret: Optional[str] = None
    shopify_store_url: Optional[str] = None

    # twitter/x config
    twitter_api_key: Optional[str] = None
    twitter_api_secret: Optional[str] = None
    twitter_access_token: Optional[str] = None
    twitter_access_token_secret: Optional[str] = None
    twitter_bearer_token: Optional[str] = None

    # linkedin config
    linkedin_access_token: Optional[str] = None
    linkedin_person_id: Optional[str] = None

    # facebook config
    facebook_access_token: Optional[str] = None
    facebook_page_id: Optional[str] = None

    # instagram config (uses facebook graph api)
    instagram_access_token: Optional[str] = None
    instagram_account_id: Optional[str] = None

    # app settings
    max_response_length: int = 3000
    response_timeout: int = 30
    enable_threading: bool = True
    show_typing_indicator: bool = True

    # scheduler settings
    scheduler_timezone: str = "UTC"

    # rate limiting
    rate_limit_per_user: int = 10
    rate_limit_window: int = 60


settings = Settings()
