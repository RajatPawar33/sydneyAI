#!/usr/bin/env python3
"""
Quick start script to verify your setup
"""
import os
import sys
from dotenv import load_dotenv

def check_environment():
    """Check if all required environment variables are set"""
    print("🔍 Checking environment variables...\n")
    
    load_dotenv()
    
    required_vars = {
        "SLACK_BOT_TOKEN": "Slack Bot Token (xoxb-...)",
        "SLACK_APP_TOKEN": "Slack App Token (xapp-...)",
        "SLACK_SIGNING_SECRET": "Slack Signing Secret",
        "OPENAI_API_KEY": "OpenAI API Key",
        "BOT_USER_ID": "Bot User ID"
    }
    
    all_set = True
    for var, description in required_vars.items():
        value = os.environ.get(var)
        if value and value != f"your-{var.lower().replace('_', '-')}-here":
            print(f"✅ {description}: Set")
        else:
            print(f"❌ {description}: NOT SET")
            all_set = False
    
    print()
    
    if all_set:
        print("✅ All environment variables are configured!")
        print("\n🚀 You're ready to start the bot:")
        print("   python bot.py")
        return True
    else:
        print("❌ Please configure missing environment variables in .env file")
        print("\n📝 Steps:")
        print("   1. Copy .env.example to .env")
        print("   2. Fill in your credentials")
        print("   3. Run this script again")
        return False

def check_dependencies():
    """Check if required packages are installed"""
    print("📦 Checking dependencies...\n")
    
    required_packages = [
        "slack_bolt",
        "langchain",
        "langgraph",
        "openai",
        "dotenv"
    ]
    
    missing = []
    for package in required_packages:
        try:
            __import__(package)
            print(f"✅ {package}")
        except ImportError:
            print(f"❌ {package}")
            missing.append(package)
    
    print()
    
    if missing:
        print("❌ Missing packages. Install them with:")
        print("   pip install -r requirements.txt")
        return False
    else:
        print("✅ All dependencies installed!")
        return True

def main():
    """Main setup verification"""
    print("=" * 50)
    print("🤖 Slack AI Bot - Setup Verification")
    print("=" * 50)
    print()
    
    # Check dependencies
    deps_ok = check_dependencies()
    print()
    
    # Check environment
    env_ok = check_environment()
    print()
    
    if deps_ok and env_ok:
        print("=" * 50)
        print("🎉 Setup complete! Ready to run the bot.")
        print("=" * 50)
        return 0
    else:
        print("=" * 50)
        print("⚠️  Setup incomplete. Please fix the issues above.")
        print("=" * 50)
        return 1

if __name__ == "__main__":
    sys.exit(main())
