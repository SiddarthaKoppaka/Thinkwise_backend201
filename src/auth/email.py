from fastapi_mail import FastMail, MessageSchema, ConnectionConfig
from src.core.config import settings  # your settings

conf = ConnectionConfig(
    MAIL_USERNAME   = settings.SMTP_USER,
    MAIL_PASSWORD   = settings.SMTP_PASSWORD,
    MAIL_FROM       = settings.EMAILS_FROM,
    MAIL_SERVER     = settings.SMTP_HOST,
    MAIL_PORT       = settings.SMTP_PORT,
    MAIL_FROM_NAME = 'ThinkWise AI Team',

    # new flag names in fastapi-mail v2+
    MAIL_STARTTLS   = True,   # was MAIL_TLS
    MAIL_SSL_TLS    = False,  # was MAIL_SSL

    USE_CREDENTIALS = True,   # ensure creds are used
    VALIDATE_CERTS  = True,   # optional, defaults to True
)
fm = FastMail(conf)

async def send_email(subject: str, recipients: list[str], body: str):
    message = MessageSchema(
        subject=subject,
        recipients=recipients,
        body=body,
        subtype="html",
    )
    await fm.send_message(message)