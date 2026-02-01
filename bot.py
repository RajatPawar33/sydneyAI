import os
import re
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
from dotenv import load_dotenv
from agent import SlackAIAgent

# Load environment variables
load_dotenv()

# Initialize Slack app
app = App(
    token=os.environ.get("SLACK_BOT_TOKEN"),
    signing_secret=os.environ.get("SLACK_SIGNING_SECRET")
)

# Initialize AI agent
ai_agent = SlackAIAgent(
    model_name="llama3:8b",
    temperature=0.7
)

# ai_agent = SlackAIAgent(
#     model_name="meta-llama/Llama-2-7b-chat-hf",
#     temperature=0.7
# )

# Store bot user ID
BOT_USER_ID = os.environ.get("BOT_USER_ID")


def get_user_info(client, user_id: str) -> dict:
    """Fetch user information from Slack"""
    try:
        result = client.users_info(user=user_id)
        return result["user"]
    except Exception as e:
        print(f"Error fetching user info: {e}")
        return {}


def get_channel_info(client, channel_id: str) -> dict:
    """Fetch channel information from Slack"""
    try:
        result = client.conversations_info(channel=channel_id)
        return result["channel"]
    except Exception as e:
        print(f"Error fetching channel info: {e}")
        return {}


def extract_message_text(text: str, bot_user_id: str) -> str:
    """Extract the actual message text by removing bot mentions"""
    # Remove bot mention
    mention_pattern = f"<@{bot_user_id}>"
    cleaned_text = re.sub(mention_pattern, "", text).strip()
    return cleaned_text


@app.event("app_mention")
def handle_mention(event, say, client):
    """Handle when the bot is mentioned in a channel"""
    try:
        # Extract event data
        user_id = event["user"]
        channel_id = event["channel"]
        text = event["text"]
        thread_ts = event.get("thread_ts", event["ts"])
        
        # Show typing indicator
        client.chat_postMessage(
            channel=channel_id,
            thread_ts=thread_ts,
            text="Thinking... 🤔"
        )
        
        # Get context
        user_info = get_user_info(client, user_id)
        channel_info = get_channel_info(client, channel_id)
        
        # Extract clean message
        message = extract_message_text(text, BOT_USER_ID)
        
        # Get AI response
        response = ai_agent.run(
            message=message,
            user_info=user_info,
            channel_info=channel_info
        )
        
        # Delete typing indicator
        # Note: In production, you'd want to store and delete the typing message
        
        # Send response in thread
        say(
            text=response,
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
    """Handle direct messages to the bot"""
    try:
        # Only respond to DMs (not channel messages)
        if message.get("channel_type") != "im":
            return
        
        # Ignore bot messages
        if message.get("bot_id"):
            return
            
        user_id = message["user"]
        text = message["text"]
        
        # Show typing indicator
        client.chat_postMessage(
            channel=message["channel"],
            text="Thinking... 🤔"
        )
        
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
    """Handle message events (required for message listener)"""
    logger.debug(body)


@app.command("/ai-help")
def handle_help_command(ack, respond):
    """Handle /ai-help slash command"""
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
    """Start the Slack bot"""
    try:
        # Validate environment variables
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
        
        # Start the bot using Socket Mode
        handler = SocketModeHandler(app, os.environ["SLACK_APP_TOKEN"])
        handler.start()
        
    except Exception as e:
        print(f"Error starting bot: {e}")


if __name__ == "__main__":
    main()
