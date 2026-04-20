import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os
from dotenv import load_dotenv
import random
import string

load_dotenv()

SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", 587))
SMTP_USER = os.getenv("SMTP_USER")
SMTP_PASS = os.getenv("SMTP_PASS")

def generate_otp(length=6):
    """Generate a random numeric OTP."""
    return "".join(random.choices(string.digits, k=length))

def send_otp_email(email_to: str, otp: str):
    """Send an OTP email to the user."""
    if not SMTP_USER or not SMTP_PASS:
        print("SMTP credentials not configured. Skipping email send.")
        return False

    message = MIMEMultipart()
    message["From"] = f"Reference Agent <{SMTP_USER}>"
    message["To"] = email_to
    message["Subject"] = "Your Verification Code - Reference Agent"

    body = f"""
    <html>
      <body style="font-family: sans-serif; line-height: 1.6; color: #333;">
        <div style="max-width: 600px; margin: 0 auto; padding: 20px; border: 1px solid #eee; border-radius: 10px;">
          <h2 style="color: #2563eb; text-align: center;">Reference Agent Verification</h2>
          <p>Hello,</p>
          <p>Thank you for using Reference Agent. Use the following code to complete your verification:</p>
          <div style="background: #f3f4f6; padding: 20px; text-align: center; border-radius: 8px; margin: 20px 0;">
            <span style="font-size: 32px; font-weight: bold; letter-spacing: 5px; color: #1f2937;">{otp}</span>
          </div>
          <p>This code will expire in 10 minutes. If you did not request this code, please ignore this email.</p>
          <hr style="border: none; border-top: 1px solid #eee; margin: 20px 0;" />
          <p style="font-size: 12px; color: #6b7280; text-align: center;">&copy; 2026 Reference Agent. Part of Route Optima Project.</p>
        </div>
      </body>
    </html>
    """
    message.attach(MIMEText(body, "html"))

    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASS)
            server.send_message(message)
        return True
    except Exception as e:
        print(f"Failed to send email: {e}")
        return False
