import logging
import httpx
from ..config import get_settings

log = logging.getLogger("sanjeevani.email")
settings = get_settings()

_WRAP = """<div style="font-family:Arial,sans-serif;max-width:520px;margin:auto;padding:24px;color:#0f172a">
<h2 style="color:#0f766e;margin:0 0 12px">Sanjeevani AI</h2>{body}
<p style="color:#64748b;font-size:12px;margin-top:28px">If you did not request this, you can ignore this email.</p></div>"""


def send_email(to: str, subject: str, body_html: str, dev_hint: str = "") -> bool:
    """Brevo transactional API. Without BREVO_API_KEY the message is logged (development convenience)."""
    if not settings.brevo_api_key:
        log.warning("[email disabled] to=%s subject=%s %s", to, subject, dev_hint)
        return False
    try:
        r = httpx.post("https://api.brevo.com/v3/smtp/email", timeout=15,
                       headers={"api-key": settings.brevo_api_key, "accept": "application/json", "content-type": "application/json"},
                       json={"sender": {"name": settings.brevo_sender_name, "email": settings.brevo_sender_email},
                             "to": [{"email": to}], "subject": subject, "htmlContent": _WRAP.format(body=body_html)})
        if r.status_code >= 300:
            log.error("Brevo error %s: %s", r.status_code, r.text[:300]); return False
        return True
    except Exception as e:  # never break the request because email failed
        log.error("Brevo exception: %s", e); return False


def _btn(url: str, label: str) -> str:
    return f'<p><a href="{url}" style="background:#0f766e;color:#fff;padding:12px 20px;border-radius:10px;text-decoration:none;display:inline-block">{label}</a></p><p style="font-size:12px;color:#64748b;word-break:break-all">{url}</p>'


def send_verification(to: str, token: str):
    url = f"{settings.frontend_url.rstrip('/')}/verify-email?token={token}"
    send_email(to, "Verify your email - Sanjeevani AI", f"<p>Welcome! Please confirm your email address to activate your account.</p>{_btn(url, 'Verify email')}", url)


def send_reset(to: str, token: str):
    url = f"{settings.frontend_url.rstrip('/')}/reset-password?token={token}"
    send_email(to, "Reset your password - Sanjeevani AI", f"<p>Use the button below to choose a new password. The link is valid for 30 minutes.</p>{_btn(url, 'Reset password')}", url)


def send_otp(to: str, code: str):
    send_email(to, "Your Sanjeevani AI sign-in code", f"<p>Your one-time sign-in code is:</p><p style='font-size:28px;letter-spacing:6px;font-weight:700'>{code}</p><p>It expires in 10 minutes.</p>", code)
