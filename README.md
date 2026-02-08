# slack marketing agent

production-grade slack agent for msme marketing automation

## features

- **email outreach campaigns**
  - collect customer emails from database or shopify
  - generate personalized email content
  - schedule bulk email sends
  
- **social media management**
  - post to twitter, linkedin, facebook, instagram
  - schedule posts across platforms
  - multi-platform posting
  - platform-specific content optimization
  - manage content calendar

- **task scheduling**
  - schedule recurring tasks
  - set reminders
  - automate workflows

- **ai-powered assistance**
  - marketing strategy advice
  - campaign analysis
  - content generation

## architecture

```
slack_agent/
├── bot.py                    # main application
├── config/
│   └── settings.py          # pydantic settings
├── core/
│   ├── agent.py             # ai agent with langchain
│   └── handler.py           # slack event handlers
├── services/
│   ├── database.py          # mongodb async operations
│   ├── cache.py             # redis caching
│   ├── email.py             # email sending
│   ├── shopify.py           # shopify integration
│   ├── scheduler.py         # task scheduling
│   ├── social_media_manager.py  # unified social media interface
│   └── social/              # platform clients
│       ├── twitter.py
│       ├── linkedin.py
│       ├── facebook.py
│       └── instagram.py
├── models/
│   └── schemas.py           # pydantic models
├── tools/
│   └── marketing_tools.py   # marketing operations
├── utils/
│   └── helpers.py           # utility functions
└── docs/
    ├── SOCIAL_MEDIA_SETUP.md
    └── SOCIAL_MEDIA_EXAMPLES.md
```

## setup

### prerequisites

- python 3.10+
- mongodb
- redis
- slack workspace with bot configured

### installation

1. clone repository
```bash
git clone <repo>
cd slack_agent
```

2. install dependencies
```bash
pip install -r requirements.txt
```

3. configure environment
```bash
cp .env.example .env
# edit .env with your credentials
```

4. start services
```bash
# start mongodb
mongod

# start redis
redis-server
```

5. run bot
```bash
python bot.py
```

## slack app setup

1. create slack app at api.slack.com/apps
2. enable socket mode
3. add bot token scopes:
   - `app_mentions:read`
   - `chat:write`
   - `im:history`
   - `im:read`
   - `users:read`
   - `channels:history`
4. install app to workspace
5. copy tokens to .env

## social media setup

see detailed guide: [docs/SOCIAL_MEDIA_SETUP.md](docs/SOCIAL_MEDIA_SETUP.md)

**supported platforms:**
- twitter/x
- linkedin
- facebook
- instagram

**quick setup:**

1. get api credentials for each platform
2. add to .env file
3. verify: `@bot check accounts`

see [docs/SOCIAL_MEDIA_EXAMPLES.md](docs/SOCIAL_MEDIA_EXAMPLES.md) for usage.

## usage examples

### email outreach

```
@bot collect emails from last 30 days with min 2 orders
@bot generate promotional email for summer sale
@bot send campaign now
```

### social media

```
@bot post now on twitter: check out our new feature
@bot schedule linkedin post for tomorrow 3pm about hiring
@bot post on twitter and linkedin: we're launching soon
@bot check accounts
@bot generate facebook post about our sale
```

### general marketing

```
@bot help me plan q1 marketing strategy
@bot analyze our last campaign performance
@bot suggest content ideas for this week
```

## configuration

edit `config/settings.py` or `.env` for:
- ai model selection
- rate limiting
- email templates
- scheduler timezone
- response length limits

## database schema

### customers
```json
{
  "email": "string",
  "name": "string",
  "total_orders": "int",
  "created_at": "datetime",
  "tags": ["string"]
}
```

### campaigns
```json
{
  "id": "string",
  "title": "string",
  "recipients": ["EmailRecipient"],
  "subject": "string",
  "body": "string",
  "status": "string",
  "sent_count": "int"
}
```

### scheduled_tasks
```json
{
  "id": "string",
  "task_type": "string",
  "description": "string",
  "scheduled_at": "datetime",
  "status": "string"
}
```

## development

### code style
- lowercase comments only
- no triple-quote docstrings
- async/await for all io operations
- pydantic for validation
- modular design

### adding new tools

1. create tool class in `tools/`
2. implement async methods
3. register in `core/handler.py`
4. add command patterns to agent

### testing

```bash
# test mongodb connection
python -c "from services.database import db_service; import asyncio; asyncio.run(db_service.connect())"

# test redis connection
python -c "from services.cache import cache_service; import asyncio; asyncio.run(cache_service.connect())"
```

## deployment

### docker
```dockerfile
FROM python:3.10-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
CMD ["python", "bot.py"]
```

### environment variables
ensure all required env vars are set in production

### monitoring
- check mongodb connections
- monitor redis memory
- track api rate limits
- log errors to file

## troubleshooting

**bot not responding**
- check slack tokens
- verify socket mode enabled
- ensure services running

**email not sending**
- verify smtp credentials
- check app password (gmail)
- test email service independently

**database errors**
- verify mongodb running
- check connection string
- ensure collections exist
