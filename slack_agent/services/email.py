import hashlib
import hmac
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx
from config.settings import settings
from models.schemas import EmailRecipient


class MailgunClient:
    def __init__(self):
        self.api_key = settings.mailgun_api_key
        self.domain = settings.mailgun_domain
        self.from_email = settings.mailgun_from_email
        self.from_name = settings.mailgun_from_name
        self.base_url = f"https://api.mailgun.net/v3/{self.domain}"
        self.from_address = f"{self.from_name} <{self.from_email}>"

    def _auth(self):
        return ("api", self.api_key)

    # --- core send methods ---

    async def send(
        self,
        to: str | List[str],
        subject: str,
        text: str,
        html: Optional[str] = None,
        reply_to: Optional[str] = None,
        tags: Optional[List[str]] = None,
        tracking_opens: bool = True,
        tracking_clicks: bool = True,
        variables: Optional[Dict[str, str]] = None,
    ) -> Dict:
        # send a single email with optional tracking and recipient variables
        if not self.api_key or not self.domain:
            raise ValueError("mailgun credentials not configured")

        data: Dict[str, Any] = {
            "from": self.from_address,
            "to": to if isinstance(to, list) else [to],
            "subject": subject,
            "text": text,
            "o:tracking-opens": "yes" if tracking_opens else "no",
            "o:tracking-clicks": "yes" if tracking_clicks else "no",
        }

        if html:
            data["html"] = html
        if reply_to:
            data["h:Reply-To"] = reply_to
        if tags:
            # mailgun supports up to 3 tags per message
            data["o:tag"] = tags[:3]
        if variables:
            # recipient variables for personalisation: {"email": {"name": "John"}}
            import json

            data["recipient-variables"] = json.dumps(variables)

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/messages",
                auth=self._auth(),
                data=data,
            )

            if response.status_code == 200:
                body = response.json()
                return {
                    "success": True,
                    "message_id": body.get("id"),
                    "message": body.get("message"),
                }
            else:
                return {
                    "success": False,
                    "error": response.text,
                    "status_code": response.status_code,
                }

    async def send_with_attachment(
        self,
        to: str,
        subject: str,
        text: str,
        attachment_path: str,
        html: Optional[str] = None,
        tags: Optional[List[str]] = None,
    ) -> Dict:
        # send email with a file attachment
        if not self.api_key or not self.domain:
            raise ValueError("mailgun credentials not configured")

        file_path = Path(attachment_path)
        if not file_path.exists():
            raise FileNotFoundError(f"attachment not found: {attachment_path}")

        data: Dict[str, Any] = {
            "from": self.from_address,
            "to": [to],
            "subject": subject,
            "text": text,
            "o:tracking-opens": "yes",
        }
        if html:
            data["html"] = html
        if tags:
            data["o:tag"] = tags[:3]

        async with httpx.AsyncClient() as client:
            with open(file_path, "rb") as f:
                response = await client.post(
                    f"{self.base_url}/messages",
                    auth=self._auth(),
                    data=data,
                    files={"attachment": (file_path.name, f)},
                )

            if response.status_code == 200:
                body = response.json()
                return {"success": True, "message_id": body.get("id")}
            else:
                return {"success": False, "error": response.text}

    async def send_template(
        self,
        to: str,
        subject: str,
        template_name: str,
        variables: Dict[str, str],
        tags: Optional[List[str]] = None,
    ) -> Dict:
        # send using a pre-built mailgun template
        if not self.api_key or not self.domain:
            raise ValueError("mailgun credentials not configured")

        data: Dict[str, Any] = {
            "from": self.from_address,
            "to": [to],
            "subject": subject,
            "template": template_name,
            "t:variables": str(variables),
            "o:tracking-opens": "yes",
            "o:tracking-clicks": "yes",
        }
        if tags:
            data["o:tag"] = tags[:3]

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/messages",
                auth=self._auth(),
                data=data,
            )

            if response.status_code == 200:
                body = response.json()
                return {"success": True, "message_id": body.get("id")}
            else:
                return {"success": False, "error": response.text}

    async def schedule_send(
        self,
        to: str | List[str],
        subject: str,
        text: str,
        deliver_at: str,
        html: Optional[str] = None,
        tags: Optional[List[str]] = None,
    ) -> Dict:
        # schedule a future send using mailgun's o:deliverytime
        # deliver_at: RFC 2822 formatted string e.g. "Fri, 01 Jan 2026 09:00:00 UTC"
        if not self.api_key or not self.domain:
            raise ValueError("mailgun credentials not configured")

        data: Dict[str, Any] = {
            "from": self.from_address,
            "to": to if isinstance(to, list) else [to],
            "subject": subject,
            "text": text,
            "o:deliverytime": deliver_at,
            "o:tracking-opens": "yes",
            "o:tracking-clicks": "yes",
        }
        if html:
            data["html"] = html
        if tags:
            data["o:tag"] = tags[:3]

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/messages",
                auth=self._auth(),
                data=data,
            )

            if response.status_code == 200:
                body = response.json()
                return {
                    "success": True,
                    "message_id": body.get("id"),
                    "scheduled_at": deliver_at,
                }
            else:
                return {"success": False, "error": response.text}

    async def send_bulk(
        self,
        recipients: List[EmailRecipient],
        subject: str,
        body_template: str,
        html_template: Optional[str] = None,
        tags: Optional[List[str]] = None,
    ) -> Dict:
        # bulk send with per-recipient personalisation via recipient-variables
        # uses single api call with batch addressing
        if not recipients:
            return {"sent": 0, "failed": 0, "errors": []}

        results = {"sent": 0, "failed": 0, "errors": [], "message_ids": []}

        # mailgun batch limit is 1000 recipients per call
        batch_size = 1000
        batches = [
            recipients[i : i + batch_size]
            for i in range(0, len(recipients), batch_size)
        ]

        for batch in batches:
            to_list = [r.email for r in batch]

            # build recipient-variables for personalisation
            import json

            rec_vars = {
                r.email: {
                    "name": r.name or r.email.split("@")[0],
                    "email": r.email,
                    "customer_id": r.customer_id or "",
                }
                for r in batch
            }

            # personalise body with %recipient.name% mailgun syntax
            personalised_text = body_template.replace(
                "{name}", "%recipient.name%"
            ).replace("{email}", "%recipient.email%")
            personalised_html = None
            if html_template:
                personalised_html = html_template.replace(
                    "{name}", "%recipient.name%"
                ).replace("{email}", "%recipient.email%")

            data: Dict[str, Any] = {
                "from": self.from_address,
                "to": to_list,
                "subject": subject,
                "text": personalised_text,
                "recipient-variables": json.dumps(rec_vars),
                "o:tracking-opens": "yes",
                "o:tracking-clicks": "yes",
            }
            if personalised_html:
                data["html"] = personalised_html
            if tags:
                data["o:tag"] = tags[:3]

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/messages",
                    auth=self._auth(),
                    data=data,
                )

                if response.status_code == 200:
                    body = response.json()
                    results["sent"] += len(batch)
                    results["message_ids"].append(body.get("id"))
                else:
                    results["failed"] += len(batch)
                    results["errors"].append(f"batch failed: {response.text}")

        return results

    # --- analytics methods ---

    async def get_stats(
        self,
        event: str = "delivered,opened,clicked,failed",
        days: int = 7,
        tags: Optional[List[str]] = None,
    ) -> Dict:
        # get aggregate stats for given events in past N days
        params: Dict[str, Any] = {
            "event": event,
            "duration": f"{days}d",
        }
        if tags:
            params["tags"] = ",".join(tags)

        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/stats/total",
                auth=self._auth(),
                params=params,
            )

            if response.status_code == 200:
                return response.json()
            return {}

    async def get_message_events(
        self,
        message_id: Optional[str] = None,
        event_filter: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict]:
        # get events for a specific message or filtered by type
        # event_filter: accepted | rejected | delivered | failed | opened | clicked | unsubscribed | complained
        params: Dict[str, Any] = {"limit": limit}
        if message_id:
            params["message-id"] = message_id
        if event_filter:
            params["event"] = event_filter

        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/events",
                auth=self._auth(),
                params=params,
            )

            if response.status_code == 200:
                return response.json().get("items", [])
            return []

    async def get_campaign_stats(self, tag: str) -> Dict:
        # get full stats for a campaign by its tag
        stats = await self.get_stats(
            event="delivered,opened,clicked,failed,unsubscribed,complained",
            days=30,
            tags=[tag],
        )

        items = stats.get("stats", [])
        totals = {
            "delivered": 0,
            "opened": 0,
            "clicked": 0,
            "failed": 0,
            "unsubscribed": 0,
            "complained": 0,
        }

        for item in items:
            for key in totals:
                totals[key] += item.get(key, {}).get("total", 0)

        delivered = totals["delivered"]
        totals["open_rate"] = (
            round(totals["opened"] / delivered * 100, 2) if delivered > 0 else 0
        )
        totals["click_rate"] = (
            round(totals["clicked"] / delivered * 100, 2) if delivered > 0 else 0
        )
        totals["tag"] = tag

        return totals

    async def get_unsubscribes(self, limit: int = 100) -> List[Dict]:
        # get list of unsubscribed addresses
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/unsubscribes",
                auth=self._auth(),
                params={"limit": limit},
            )

            if response.status_code == 200:
                return response.json().get("items", [])
            return []

    async def add_unsubscribe(self, email: str, tag: str = "*") -> bool:
        # manually add to unsubscribe list (tag="*" means global)
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/unsubscribes",
                auth=self._auth(),
                data={"address": email, "tag": tag},
            )
            return response.status_code == 200

    async def delete_unsubscribe(self, email: str) -> bool:
        # remove from unsubscribe list (re-enable sends)
        async with httpx.AsyncClient() as client:
            response = await client.delete(
                f"{self.base_url}/unsubscribes/{email}",
                auth=self._auth(),
            )
            return response.status_code == 200

    async def get_bounces(self, limit: int = 100) -> List[Dict]:
        # get hard-bounced addresses
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/bounces",
                auth=self._auth(),
                params={"limit": limit},
            )

            if response.status_code == 200:
                return response.json().get("items", [])
            return []

    # --- webhook signature verification ---

    def verify_webhook(self, timestamp: str, token: str, signature: str) -> bool:
        # verify mailgun webhook authenticity — call this in your webhook endpoint
        if not settings.mailgun_webhook_signing_key:
            return False

        value = f"{timestamp}{token}".encode()
        expected = hmac.new(
            settings.mailgun_webhook_signing_key.encode(),
            value,
            hashlib.sha256,
        ).hexdigest()

        # also guard against replay attacks (5 min window)
        age = abs(int(time.time()) - int(timestamp))
        if age > 300:
            return False

        return hmac.compare_digest(expected, signature)


mailgun_client = MailgunClient()

# keep backward-compat alias so existing imports don't break
email_service = mailgun_client
