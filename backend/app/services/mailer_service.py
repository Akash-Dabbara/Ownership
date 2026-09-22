import os
import smtplib
from email.mime.text import MIMEText

SMTP_HOST = os.environ.get("SMTP_HOST")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
SMTP_USERNAME = os.environ.get("SMTP_USERNAME")
SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD")
SMTP_FROM_EMAIL = os.environ.get("SMTP_FROM_EMAIL", SMTP_USERNAME)


def send_email(to_email: str, subject: str, body: str) -> bool:
    """
    Sends a plain-text email via SMTP.

    Works with Gmail SMTP, SendGrid's SMTP relay, Mailgun, or any
    standard SMTP provider — configure via environment variables:

        SMTP_HOST
        SMTP_PORT           (defaults to 587)
        SMTP_USERNAME
        SMTP_PASSWORD
        SMTP_FROM_EMAIL     (defaults to SMTP_USERNAME)

    If these are not set, the email is logged to the console
    instead of failing — so the rest of the app keeps working
    while email is being set up. Returns True if actually sent,
    False if it only logged.
    """

    if not SMTP_HOST or not SMTP_USERNAME or not SMTP_PASSWORD:
        print(
            "[MAILER NOT CONFIGURED — set SMTP_HOST/SMTP_USERNAME/"
            "SMTP_PASSWORD to send real emails]\n"
            f"To: {to_email}\nSubject: {subject}\n\n{body}\n"
        )
        return False

    message = MIMEText(body)
    message["Subject"] = subject
    message["From"] = SMTP_FROM_EMAIL
    message["To"] = to_email

    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=10) as server:
            server.starttls()
            server.login(SMTP_USERNAME, SMTP_PASSWORD)
            server.sendmail(SMTP_FROM_EMAIL, [to_email], message.as_string())
        return True
    except Exception as exc:
        print(f"[MAILER ERROR] Failed to send email to {to_email}: {exc}")
        return False