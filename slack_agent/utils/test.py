import os
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail, TrackingSettings, ClickTracking, OpenTracking

def send_sendgrid_click_test():
    # ==================== CONFIGURATION ====================
    # Replace these strings with your actual values
      
    FROM_EMAIL = "rajatpawar249@gmail.com"  # Must be verified in your SendGrid Account
    TO_EMAIL = "rv4012.33@gmail.com"  # Where you will receive and click the test email
    
    # Put your active public NGROK base URL here (e.g., https://abcd-1234.ngrok-free.app)
    NGROK_BASE_URL = "https://gooey-morphine-swiftly.ngrok-free.dev" 
    
    # Temporary placeholder URL destination where the user lands at the end
    TEMPORARY_DESTINATION_URL = "https://en.wikipedia.org/wiki/Artificial_intelligence"
    # =======================================================

    # Construct the tracking link exactly how your FastAPI endpoint expects it
    campaign_id = "test_click_verification_999"
    query_params = (
        f"?email={TO_EMAIL}"
        f"&name=DeveloperTest"
        f"&campaign_id={campaign_id}"
        f"&product_title=Test_AI_Puffer_Jacket"
        f"&product_type=Outerwear"
        f"&redirect_url={TEMPORARY_DESTINATION_URL}"
    )
    final_url = "https://en.wikipedia.org/wiki/Artificial_intelligence"

    # Build the HTML body with a clear clickable link anchor tag
    html_content = f"""
<html>
  <body>
    <h2>SendGrid Click Tracking Test</h2>
    <a href="{final_url}" 
       style="background-color: blue; color: white; padding: 10px;">
       Click Me
    </a>
  </body>
</html>
"""
    # Initialize the SendGrid Mail object
    message = Mail(
        from_email=FROM_EMAIL,
        to_emails=TO_EMAIL,
        subject="🚀 Test: Verify SendGrid Click Events",
        html_content=html_content
    )

    # CRITICAL: Force Enable SendGrid's Tracking Settings
    tracking_settings = TrackingSettings()
    tracking_settings.click_tracking = ClickTracking(enable=True, enable_text=True)
    tracking_settings.open_tracking = OpenTracking(enable=True)
    message.tracking_settings = tracking_settings

    try:
        print("Connecting to SendGrid API...")
        sg = SendGridAPIClient(SENDGRID_API_KEY)
        response = sg.send(message)
        
        print("\n=== Success ===")
        print(f"Status Code: {response.status_code}")
        print("Email successfully dispatched. Please check your inbox!")
        
    except Exception as e:
        print(f"\nAPI Error: {e}")

if __name__ == "__main__":
    send_sendgrid_click_test()