import re
from datetime import datetime, timedelta
from typing import Dict, List, Optional

import dateparser


def extract_slack_mentions(text: str) -> List[str]:
    # extract user mentions <@U123456>
    pattern = r"<@([A-Z0-9]+)>"
    return re.findall(pattern, text)


def clean_slack_text(text: str, bot_user_id: str = None) -> str:
    # remove bot mentions
    if bot_user_id:
        text = re.sub(f"<@{bot_user_id}>", "", text)

    # remove channel mentions
    text = re.sub(r"<#[A-Z0-9]+\|([^>]+)>", r"#\1", text)

    # remove link formatting
    text = re.sub(r"<(https?://[^|>]+)\|([^>]+)>", r"\2", text)
    text = re.sub(r"<(https?://[^>]+)>", r"\1", text)

    return " ".join(text.split()).strip()


def format_slack_message(text: str, max_length: int = 3000) -> str:
    if len(text) <= max_length:
        return text

    truncated = text[: max_length - 50]
    return f"{truncated}\n\n_[message truncated]_"


def parse_date_from_text(text: str) -> Optional[datetime]:
    # try to extract date from natural language
    # "tomorrow at 3pm", "next monday", "2024-01-15"

    # use dateparser library for natural language
    parsed = dateparser.parse(text, settings={"PREFER_DATES_FROM": "future"})
    return parsed


def extract_email_from_text(text: str) -> List[str]:
    # extract email addresses from text
    pattern = r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"
    return re.findall(pattern, text)


def parse_date_range_from_text(text: str) -> Optional[Dict[str, datetime]]:
    # extract date range "from jan 1 to jan 31"
    # "last week", "last month", "last 30 days"

    text_lower = text.lower()

    if "last week" in text_lower:
        end_date = datetime.now()
        start_date = end_date - timedelta(days=7)
        return {"start_date": start_date, "end_date": end_date}

    if "last month" in text_lower:
        end_date = datetime.now()
        start_date = end_date - timedelta(days=30)
        return {"start_date": start_date, "end_date": end_date}

    # match pattern "from X to Y"
    match = re.search(r"from\s+(.+?)\s+to\s+(.+?)(?:\s|$)", text_lower)
    if match:
        start_str, end_str = match.groups()
        start_date = dateparser.parse(start_str)
        end_date = dateparser.parse(end_str)

        if start_date and end_date:
            return {"start_date": start_date, "end_date": end_date}

    return None


def validate_email(email: str) -> bool:
    pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
    return re.match(pattern, email) is not None


def truncate_text(text: str, max_length: int, suffix: str = "...") -> str:
    if len(text) <= max_length:
        return text
    return text[: max_length - len(suffix)] + suffix


def create_slack_blocks(
    title: str = None, content: str = None, fields: List[Dict] = None
) -> List[Dict]:
    blocks = []

    if title:
        blocks.append({"type": "header", "text": {"type": "plain_text", "text": title}})

    if content:
        blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": content}})

    if fields:
        blocks.append(
            {
                "type": "section",
                "fields": [
                    {"type": "mrkdwn", "text": f"*{k}*\n{v}"}
                    for field in fields
                    for k, v in field.items()
                ],
            }
        )

    return blocks
