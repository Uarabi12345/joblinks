import os
import requests
from dotenv import load_dotenv

load_dotenv()

# We now use Brevo's API instead of SMTP to bypass Render's firewall
BREVO_API_KEY = os.getenv("BREVO_API_KEY")
FROM_EMAIL = os.getenv("SMTP_EMAIL") # This will be your Brevo sender email
FROM_NAME = "JobLinks"

def send_email(to_email: str, subject: str, body: str):
    if not BREVO_API_KEY or not FROM_EMAIL:
        print("⚠️ EMAIL NOT SENT: Brevo API key or sender email missing in .env")
        return False

    url = "https://api.brevo.com/v3/smtp/email"
    headers = {
        "accept": "application/json",
        "api-key": BREVO_API_KEY,
        "content-type": "application/json"
    }
    
    # We format the text body into basic HTML so it looks nice in the email
    html_body = f"<html><body><p>{body.replace(chr(10), '<br>')}</p></body></html>"
    
    payload = {
        "sender": {"name": FROM_NAME, "email": FROM_EMAIL},
        "to": [{"email": to_email}],
        "subject": subject,
        "htmlContent": html_body
    }

    try:
        response = requests.post(url, json=payload, headers=headers)
        response.raise_for_status() 
        print(f"✅ Email sent to {to_email} via Brevo API")
        return True
    except requests.exceptions.RequestException as e:
        print(f"❌ Failed to send email: {e}")
        if response.text:
            print(f"Error details: {response.text}")
        return False