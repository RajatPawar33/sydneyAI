import base64
import json
from pathlib import Path
from typing import Any, Dict, List, Optional
from datetime import datetime

from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import (
    Mail, Attachment, FileContent, FileName, FileType, 
    Disposition, Personalization, To, Substitution, TrackingSettings, ClickTracking, OpenTracking, CustomArg, SendAt
)

from slack_agent.config.settings import settings
from slack_agent.models.schemas import EmailRecipient

class MailgunClient:  # Kept name for compatibility
    def __init__(self):
        self.api_key = settings.sendgrid_api_key
        self.from_email = settings.sendgrid_from_email
        self.from_name = settings.sendgrid_from_name
        self.client = SendGridAPIClient(api_key=self.api_key)
        self.from_address = (self.from_email, self.from_name)

    def _get_default_tracking(self, opens: bool = True, clicks: bool = True) -> TrackingSettings:
        """Helper to create consistent tracking settings."""
        tracking_settings = TrackingSettings()
        tracking_settings.click_tracking = ClickTracking(clicks, clicks)
        tracking_settings.open_tracking = OpenTracking(opens)
        return tracking_settings

    def _ensure_html_structure(self, html: Optional[str]) -> Optional[str]:
        """
        Ensures HTML has a body tag. SendGrid injects the tracking pixel 
        before the </body> tag. Fragments without body tags may fail to track.
        """
        if not html:
            return None
        if "</body>" not in html.lower():
            return f"<html><body>{html}</body></html>"
        return html

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
            message = Mail(
                from_email=self.from_address,
                to_emails=to if isinstance(to, list) else [to],
                subject=subject,
                plain_text_content=text,
                html_content=self._ensure_html_structure(html)
            )
            
            # Use explicit tracking settings
            message.tracking_settings = self._get_default_tracking(tracking_opens, tracking_clicks)
            
            if reply_to:
                message.reply_to = reply_to
                
            if tags:
                for tag in tags[:10]:
                    message.add_custom_arg(CustomArg(f"tag_{tag}", tag))

            # DEBUG: Print the JSON payload to verify 'tracking_settings' are present
            # You can inspect this output to see exactly what is sent to SendGrid
            print("--- SENDGRID API PAYLOAD DEBUG ---")
            print(json.dumps(message.get(), indent=2))

            try:
                response = self.client.send(message)
                return {
                    "success": response.status_code in [200, 201, 202],
                    "message_id": response.headers.get("X-Message-Id"),
                    "status_code": response.status_code
                }
            except Exception as e:
                return {"success": False, "error": str(e)}

    async def send_with_attachment(
        self,
        to: str,
        subject: str,
        text: str,
        attachment_path: str,
        html: Optional[str] = None,
        tags: Optional[List[str]] = None,
    ) -> Dict:
        file_path = Path(attachment_path)
        if not file_path.exists():
            raise FileNotFoundError(f"attachment not found: {attachment_path}")

        message = Mail(
            from_email=self.from_address,
            to_emails=to,
            subject=subject,
            plain_text_content=text,
            html_content=self._ensure_html_structure(html)
        )
        
        # Added explicit tracking
        message.tracking_settings = self._get_default_tracking()

        with open(file_path, 'rb') as f:
            data = f.read()
            encoded_file = base64.b64encode(data).decode()

        attachedFile = Attachment(
            FileContent(encoded_file),
            FileName(file_path.name),
            FileType('application/octet-stream'),
            Disposition('attachment')
        )
        message.add_attachment(attachedFile)

        try:
            response = self.client.send(message)
            return {"success": response.status_code in [200, 201, 202], "message_id": response.headers.get("X-Message-Id")}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def send_template(
        self,
        to: str,
        subject: str,
        template_id: str,
        variables: Dict[str, str],
        tags: Optional[List[str]] = None,
    ) -> Dict:
        message = Mail(
            from_email=self.from_address,
            to_emails=to
        )
        message.template_id = template_id
        message.dynamic_template_data = variables
        
        # Added explicit tracking
        message.tracking_settings = self._get_default_tracking()

        try:
            response = self.client.send(message)
            return {"success": response.status_code in [200, 201, 202], "message_id": response.headers.get("X-Message-Id")}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def schedule_send(
        self,
        to: str | List[str],
        subject: str,
        text: str,
        deliver_at: int,
        html: Optional[str] = None,
        tags: Optional[List[str]] = None,
    ) -> Dict:
        message = Mail(
            from_email=self.from_address,
            to_emails=to if isinstance(to, list) else [to],
            subject=subject,
            plain_text_content=text,
            html_content=self._ensure_html_structure(html)
        )
        message.send_at = SendAt(deliver_at)
        
        # Added explicit tracking
        message.tracking_settings = self._get_default_tracking()

        try:
            response = self.client.send(message)
            return {"success": response.status_code in [200, 201, 202], "message_id": response.headers.get("X-Message-Id")}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def send_bulk(
        self,
        recipients: List[EmailRecipient],
        subject: str,
        body_template: str,
        html_template: Optional[str] = None,
        tags: Optional[List[str]] = None,
    ) -> Dict:
        if not recipients:
            return {"sent": 0, "failed": 0, "errors": []}

        results = {"sent": 0, "failed": 0, "errors": [], "message_ids": []}
        batch_size = 1000
        
        for i in range(0, len(recipients), batch_size):
            batch = recipients[i : i + batch_size]
            
            message = Mail(
                from_email=self.from_address,
                subject=subject,
                plain_text_content=body_template,
                html_content=self._ensure_html_structure(html_template)
            )

            message.tracking_settings = self._get_default_tracking()
            
            for recipient in batch:
                p = Personalization()
                p.add_to(To(recipient.email))
                p.add_custom_arg(CustomArg("recipient_id", str(recipient.customer_id or "")))
                if tags:
                    for tag in tags[:9]:
                        p.add_custom_arg(CustomArg(f"tag_{tag}", tag))
                
                name = recipient.name or recipient.email.split("@")[0]
                p.add_substitution(Substitution("{name}", name))
                message.add_personalization(p)

            # ADDED DEBUG PRINT HERE: This is what your bot uses for campaigns
            print(f"\n--- SENDGRID BULK-SEND PAYLOAD DEBUG (Batch {i//batch_size + 1}) ---")
            print(json.dumps(message.get(), indent=2))

            try:
                response = self.client.send(message)
                if response.status_code in [200, 201, 202]:
                    results["sent"] += len(batch)
                    results["message_ids"].append(response.headers.get("X-Message-Id"))
                else:
                    error_body = response.body.decode('utf-8') if hasattr(response.body, 'decode') else str(response.body)
                    results["failed"] += len(batch)
                    results["errors"].append(f"Status {response.status_code}: {error_body}")
            except Exception as e:
                error_detail = getattr(e, 'body', str(e))
                results["failed"] += len(batch)
                results["errors"].append(str(error_detail))

        return results

    async def get_stats(self, days: int = 7) -> Dict:
        try:
            params = {'aggregated_by': 'day', 'start_date': datetime.now().strftime('%Y-%m-%d')}
            response = self.client.stats.get(query_params=params)
            return response.to_dict
        except:
            return {}

    async def get_unsubscribes(self, limit: int = 100) -> List[Dict]:
        try:
            response = self.client.asm.suppressions.get()
            return response.to_dict
        except:
            return []

    def verify_webhook(self, timestamp: str, token: str, signature: str) -> bool:
        return False

mailgun_client = MailgunClient()
email_service = mailgun_client