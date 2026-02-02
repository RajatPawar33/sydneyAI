import os
import re
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
from dotenv import load_dotenv
# from agent import SlackAIAgent
from enhanced_agent import EnhancedMarketingAgent
from config import AI_MODEL_NAME, AI_TEMPERATURE
from utils import clean_slack_formatting, format_slack_message

# Load environment variables
load_dotenv()

# Initialize Slack app
app = App(
    token=os.environ.get("SLACK_BOT_TOKEN"),
    signing_secret=os.environ.get("SLACK_SIGNING_SECRET")
)

# Initialize AI agent


ai_agent = EnhancedMarketingAgent(
    model_name=AI_MODEL_NAME,
    temperature=AI_TEMPERATURE
)




# Store bot user ID
BOT_USER_ID = os.environ.get("BOT_USER_ID")


def get_user_info(client, user_id: str) -> dict:
    
    try:
        result = client.users_info(user=user_id)
        return result["user"]
    except Exception as e:
        print(f"Error fetching user info: {e}")
        return {}


def get_channel_info(client, channel_id: str) -> dict:
    
    try:
        result = client.conversations_info(channel=channel_id)
        return result["channel"]
    except Exception as e:
        print(f"Error fetching channel info: {e}")
        return {}





@app.event("app_mention")
def handle_mention(event, say, client):
    try:
        # Extract event data
        user_id = event["user"]
        channel_id = event["channel"]
        text = event["text"]
        thread_ts = event.get("thread_ts", event["ts"])
        
        
        
        # Get context
        user_info = get_user_info(client, user_id)
        channel_info = get_channel_info(client, channel_id)
        
        # Extract clean message
        message = clean_slack_formatting(text)

       
        
        # Get AI response
        response = ai_agent.run(
            message=message,
            user_info=user_info,
            channel_info=channel_info
        )
        
        say(
            text=format_slack_message(response),
            thread_ts=thread_ts
        )

        
    except Exception as e:
        print(f"Error handling mention: {e}")
        say(
            text=f"Sorry, I encountered an error: {str(e)}",
            thread_ts=event.get("thread_ts", event["ts"])
        )


@app.message("")
def handle_direct_message(message, say, client):
    
    try:
        # Only respond to DMs (not channel messages)
        if message.get("channel_type") != "im":
            return
        
        # Ignore bot messages
        if message.get("bot_id"):
            return
            
        user_id = message["user"]
        text = message["text"]
        
        
        
        # Get user context
        user_info = get_user_info(client, user_id)
        
        # Get AI response
        response = ai_agent.run(
            message=text,
            user_info=user_info,
            channel_info={"name": "direct-message"}
        )
        
        # Send response
        say(response)
        
    except Exception as e:
        print(f"Error handling DM: {e}")
        say(f"Sorry, I encountered an error: {str(e)}")


@app.event("message")
def handle_message_events(body, logger):
   
    logger.debug(body)


@app.command("/sydney-help")
def handle_help_command(ack, respond):
    
    ack()
    
    help_text = """
    *AI Marketing Manager Bot - Help* 🤖
    
    *How to use me:*
    • Mention me in any channel: `@AI Marketing Manager your question here`
    • Send me a direct message with your question
    • Use the `/ai-help` command to see this help message
    
    *What I can help with:*
    • Marketing strategy and planning
    • Campaign analysis and optimization
    • Content ideas and brainstorming
    • Marketing analytics insights
    • General marketing questions
    
    *Tips:*
    • Be specific with your questions for better answers
    • I work best with context - tell me about your goals!
    • I'll respond in threads to keep channels organized
    
    Need something? Just tag me! 🚀
    """
    
    respond(help_text)


def main():
    
    try:
        
        required_vars = [
            "SLACK_BOT_TOKEN",
            "SLACK_APP_TOKEN",
            "SLACK_SIGNING_SECRET",
            "BOT_USER_ID"
        ]

        
        missing_vars = [var for var in required_vars if not os.environ.get(var)]
        
        if missing_vars:
            print(f"Error: Missing required environment variables: {', '.join(missing_vars)}")
            print("Please check your .env file")
            return
        
        print("🚀 Starting AI Marketing Manager Bot...")
        print(f"Bot User ID: {BOT_USER_ID}")
        
        
        handler = SocketModeHandler(app, os.environ["SLACK_APP_TOKEN"])
        handler.start()
        
    except Exception as e:
        print(f"Error starting bot: {e}")


if __name__ == "__main__":
    main()
