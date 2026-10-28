import smtplib
import os
from email.message import EmailMessage
from dotenv import load_dotenv

load_dotenv()

SMTP_EMAIL = os.getenv("SMTP_EMAIL")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")
SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "465"))

def send_email(to_email: str, subject: str, body: str):
    if not SMTP_EMAIL or not SMTP_PASSWORD:
        print("⚠️ EMAIL NOT SENT: SMTP credentials missing in .env")
        return False

    msg = EmailMessage()
    msg.set_content(body)
    msg['Subject'] = subject
    msg['From'] = f"JobLinks <{SMTP_EMAIL}>"
    msg['To'] = to_email

    try:
        if SMTP_PORT == 465:
            # Gmail / SSL
            with smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT) as server:
                server.login(SMTP_EMAIL, SMTP_PASSWORD)
                server.send_message(msg)
        else:
            # SMTP2GO / STARTTLS
            with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
                server.starttls()
                server.login(SMTP_EMAIL, SMTP_PASSWORD)
                server.send_message(msg)
        print(f"✅ Email sent to {to_email}")
        return True
    except Exception as e:
        print(f"❌ Failed to send email: {e}")
        return False