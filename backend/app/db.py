from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, Session, DeclarativeBase
from .config import get_settings

settings = get_settings()
_is_pg = settings.database_url.startswith("postgresql")
_kwargs = {"pool_pre_ping": True}
if _is_pg:
    # prepare_threshold=None -> works through Neon's pgbouncer (transaction pooling)
    _kwargs.update(pool_size=5, max_overflow=5, pool_recycle=240, connect_args={"prepare_threshold": None})
else:
    _kwargs["connect_args"] = {"check_same_thread": False}
engine = create_engine(settings.database_url, **_kwargs)
SessionLocal = sessionmaker(engine, expire_on_commit=False, autoflush=False)


class Base(DeclarativeBase):
    pass


@event.listens_for(Session, "after_begin")
def _apply_rls_context(session, transaction, connection):
    """Defence in depth: every transaction carries the caller identity so Postgres RLS policies can enforce isolation."""
    if not (settings.enable_rls and _is_pg):
        return
    uid, role = session.info.get("rls", ("", ""))
    connection.exec_driver_sql("select set_config('app.user_id', %s, true), set_config('app.role', %s, true)", (str(uid), role))


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


RLS_TABLES = ["patient_profiles", "face_credentials", "medications", "conditions", "allergies", "documents", "analysis_runs"]


def enable_rls(conn):
    for t in RLS_TABLES:
        conn.exec_driver_sql(f"ALTER TABLE {t} ENABLE ROW LEVEL SECURITY")
        conn.exec_driver_sql(f"ALTER TABLE {t} FORCE ROW LEVEL SECURITY")
        conn.exec_driver_sql(f"DROP POLICY IF EXISTS owner_or_admin ON {t}")
        cond = ("(user_id = nullif(current_setting('app.user_id', true), '')::uuid "
                "OR current_setting('app.role', true) = 'admin')")
        conn.exec_driver_sql(f"CREATE POLICY owner_or_admin ON {t} USING {cond} WITH CHECK {cond}")


def set_rls(db: Session, uid, role: str):
    """Set caller identity for the current AND future transactions of this session."""
    db.info["rls"] = (uid, role)
    if settings.enable_rls and _is_pg:
        db.connection().exec_driver_sql("select set_config('app.user_id', %s, true), set_config('app.role', %s, true)", (str(uid), role))
