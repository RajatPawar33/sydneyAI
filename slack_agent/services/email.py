from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import List

import aiosmtplib
from config.settings import settings
from models.schemas import EmailRecipient


class EmailService:
    def __init__(self):
        self.smtp_host = settings.smtp_host
        self.smtp_port = settings.smtp_port
        self.username = settings.smtp_username
        self.password = settings.smtp_password
        self.from_email = settings.smtp_from_email or settings.smtp_username

    async def send_email(
        self, to_email: str, subject: str, body: str, body_html: str = None
    ) -> bool:
        try:
            message = MIMEMultipart("alternative")
            message["From"] = self.from_email
            message["To"] = to_email
            message["Subject"] = subject

            # attach plain text
            message.attach(MIMEText(body, "plain"))

            # attach html if provided
            if body_html:
                message.attach(MIMEText(body_html, "html"))

            await aiosmtplib.send(
                message,
                hostname=self.smtp_host,
                port=self.smtp_port,
                username=self.username,
                password=self.password,
                start_tls=True,
            )

            return True
        except Exception as e:
            print(f"email send error: {e}")
            return False

    async def send_bulk_emails(
        self,
        recipients: List[EmailRecipient],
        subject: str,
        body_template: str,
        personalize: bool = True,
    ) -> dict:
        results = {"sent": 0, "failed": 0, "errors": []}

        for recipient in recipients:
            try:
                # personalize email body
                body = body_template
                if personalize and recipient.name:
                    body = body.replace("{name}", recipient.name)
                    body = body.replace("{email}", recipient.email)

                success = await self.send_email(recipient.email, subject, body)

                if success:
                    results["sent"] += 1
                else:
                    results["failed"] += 1
                    results["errors"].append(f"failed to send to {recipient.email}")
            except Exception as e:
                results["failed"] += 1
                results["errors"].append(f"{recipient.email}: {str(e)}")

        return results

    async def send_notification_email(
        self, to_email: str, notification_type: str, data: dict
    ) -> bool:
        # predefined notification templates
        templates = {
            "campaign_sent": {
                "subject": "Campaign Successfully Sent",
                "body": f"Your campaign has been sent to {data.get('count', 0)} recipients.",
            },
            "task_completed": {
                "subject": "Scheduled Task Completed",
                "body": f"Task '{data.get('task_name', 'Unknown')}' completed successfully.",
            },
            "error": {
                "subject": "Error Notification",
                "body": f"An error occurred: {data.get('error', 'Unknown error')}",
            },
        }

        template = templates.get(notification_type, templates["error"])
        return await self.send_email(to_email, template["subject"], template["body"])


email_service = EmailService()
