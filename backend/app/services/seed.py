import logging
from sqlalchemy import select
from sqlalchemy.orm import Session
from ..config import get_settings
from ..models import User
from ..security import hash_password

log = logging.getLogger("sanjeevani.seed")


def seed_admins(db: Session):
    """Doctor/admin accounts exist only through server configuration - there is no admin registration endpoint."""
    s = get_settings()
    for a in s.admin_list():
        email = a["email"].strip().lower()
        u = db.scalar(select(User).where(User.email == email))
        if u is None:
            db.add(User(email=email, password_hash=hash_password(a["password"]), role="admin", display_name=a.get("name") or "Doctor", email_verified=True, is_active=True))
            log.warning("Created doctor account %s", email)
        elif u.role != "admin":
            log.error("ADMIN_EMAIL %s already belongs to a patient account; refusing to promote it. Use a different email.", email)
        elif s.admin_sync_password:
            u.password_hash = hash_password(a["password"]); u.failed_attempts = 0; u.locked_until = None
            log.warning("Doctor password re-synced from environment for %s", email)
    db.commit()
