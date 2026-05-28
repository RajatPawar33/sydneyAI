from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=r".env.example", env_file_encoding="utf-8", case_sensitive=False, extra="ignore"
    )
    port: int = 8000

    # slack credentials
    slack_bot_token: str
    slack_app_token: str
    slack_signing_secret: str
    bot_user_id: str

 
    ollama_temperature: float = 0.7
   
   #tavily config
    tavily_api_key: Optional[str] = None

    # openai config
    openai_api_key: Optional[str] = None  
    openai_model: str = "gpt-4o-mini"

    # redis config
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_db: int = 0

    # mongodb config
    mongodb_uri: str = "mongodb://localhost:27017"
    mongodb_db_name: str = "sydney"

    # mailgun config
    # mailgun_api_key: Optional[str] = None
    # mailgun_domain: Optional[str] = None
    # mailgun_from_email: Optional[str] = None
    # mailgun_from_name: str = "Sydney Bot"
    # mailgun_webhook_signing_key: Optional[str] = None

# SendGrid config (Replacing Mailgun)
    sendgrid_api_key: Optional[str] = None
    sendgrid_from_email: Optional[str] = None
    sendgrid_from_name: str = "Sydney Bot"

    # youtube data api
    youtube_api_key: Optional[str] = None

    # apify (instagram discovery)
    apify_api_token: Optional[str] = None

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
    linkedin_access_token: Optional[str] ='AQXCtS-JohtjgsoYBcbomwmAaQBnFfBbWnq_VDkn4QxQEbjbJjTpsL9UGLHC1UBJUwlo7EBFhG-2IOllMFZNnS6_koNeRX3xbdgqqT3Vr-LMjQ6z5J3ktHW0sEmYzrxgPP6ZmQK_hU-oQ7Gs5PlJmRtB3GHnJ7ZNx9LY1ZImg-R8CMAR7kPOG7MjyUAGy2FOP37PwNp8x50GHtCDj3QwHqg6y--bLOExAr8ezpo6lZp9kNLNw8uOsWG4JpDKJMdWwTfAxu9nx2iRbCaLcVbxyeFaI7As_2VOXhMv9jg7PbNTjT2JVMeIzztVS0CE8b8FzTE9OxP6Ub_0TWtMKrpzJpdD4fFo9w'
    linkedin_person_id: Optional[str] = 'urn:li:person:rGDKZlW1KJ'

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
    scheduler_timezone: str = "Asia/Kolkata"

    # rate limiting
    rate_limit_per_user: int = 10
    rate_limit_window: int = 60


settings = Settings()
