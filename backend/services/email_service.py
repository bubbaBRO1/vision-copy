import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)


def _send(to: str, subject: str, html: str) -> None:
    if not settings.smtp_host:
        logger.info("[EMAIL] SMTP not configured — skipping: to=%s subject=%s", to, subject)
        return
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = settings.email_from
    msg["To"] = to
    msg.attach(MIMEText(html, "html"))
    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as s:
            s.starttls()
            if settings.smtp_user:
                s.login(settings.smtp_user, settings.smtp_password)
            s.sendmail(settings.email_from, to, msg.as_string())
    except Exception:
        logger.error("[EMAIL] Failed to send to=%s subject=%s", to, subject, exc_info=True)
        raise


def send_verification_email(to: str, token: str) -> None:
    url = f"{settings.frontend_url}/auth/verify-email?token={token}"
    _send(
        to,
        "Verify your VISION account",
        f"""
        <div style="font-family:monospace;background:#080810;color:#e8e8f0;padding:32px;">
          <h2 style="color:#00ff88;">VISION</h2>
          <p>Verify your email to activate your account:</p>
          <a href="{url}" style="color:#00cfff;">{url}</a>
          <p style="color:#6b6b8a;">Link expires in 24 hours.</p>
        </div>
        """,
    )


def send_password_reset_email(to: str, token: str) -> None:
    url = f"{settings.frontend_url}/auth/reset-password?token={token}"
    _send(
        to,
        "Reset your VISION password",
        f"""
        <div style="font-family:monospace;background:#080810;color:#e8e8f0;padding:32px;">
          <h2 style="color:#00ff88;">VISION</h2>
          <p>Reset your password:</p>
          <a href="{url}" style="color:#00cfff;">{url}</a>
          <p style="color:#6b6b8a;">Link expires in 1 hour. If you didn't request this, ignore it.</p>
        </div>
        """,
    )


def send_invite_email(to: str, invite_token: str, name: str) -> None:
    url = f"{settings.frontend_url}/signup?invite={invite_token}"
    _send(
        to,
        "You're approved — join VISION",
        f"""
        <div style="font-family:monospace;background:#080810;color:#e8e8f0;padding:32px;">
          <h2 style="color:#00ff88;">VISION</h2>
          <p>Hello {name},</p>
          <p>Your waitlist application has been approved. Create your account:</p>
          <a href="{url}" style="color:#00cfff;">{url}</a>
          <p style="color:#6b6b8a;">This invite expires in 72 hours.</p>
        </div>
        """,
    )
