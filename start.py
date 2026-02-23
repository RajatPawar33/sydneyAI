from slack_agent.config.settings import settings

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "slack_agent.bot:web_app",
        host="0.0.0.0",
        port=settings.port,
        limit_max_requests=1000,
        timeout_keep_alive=65,
        reload=True,
    )
