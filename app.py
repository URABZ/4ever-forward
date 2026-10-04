from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import re
import secrets
import smtplib
import time
from email.message import EmailMessage
from pathlib import Path
from typing import Any

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from fastapi import Cookie, FastAPI, Header, HTTPException, Request, Response
from fastapi.responses import FileResponse, RedirectResponse
from pydantic import BaseModel, Field
from sqlalchemy import BigInteger, ForeignKey, LargeBinary, String, Text, create_engine, delete, func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column

ROOT = Path(__file__).resolve().parent
ENV = os.getenv("FF_ENV", "development").lower()
PRODUCTION = ENV == "production"
COOKIE_NAME = "ff_session"
SESSION_DAYS = int(os.getenv("FF_SESSION_DAYS", "30"))
COOKIE_SECURE = os.getenv("FF_COOKIE_SECURE", "1" if PRODUCTION else "0") == "1"
MAX_STATE_BYTES = int(os.getenv("FF_MAX_STATE_BYTES", str(2 * 1024 * 1024)))
SUPPORT_EMAIL = os.getenv("FF_SUPPORT_EMAIL", "support@example.com")

def public_base_url() -> str:
    explicit = os.getenv("FF_PUBLIC_BASE_URL", "").strip().rstrip("/")
    if explicit:
        return explicit
    render_host = os.getenv("RENDER_EXTERNAL_HOSTNAME", "").strip()
    if render_host:
        return f"https://{render_host}"
    return "http://127.0.0.1:8000"

DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{ROOT / 'data' / '4ever_forward.sqlite3'}")
if DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = "postgresql+psycopg://" + DATABASE_URL[len("postgresql://"):]

SYNC_KEYS = {
    "4everForwardBackupMetaV1", "4everForwardGuidanceV1", "4everForwardMomentumV1",
    "4everForwardPartnerReferralsV1", "4everForwardPartnerUpdatesV1", "4everForwardProfileV1",
    "4everForwardResourceHealthV1", "4everForwardTasksV2", "ff_forward_access_v26",
    "ff_forward_action_v23", "ff_forward_coalition_v24", "ff_forward_commit_v30",
    "ff_forward_connect_v29", "ff_forward_guidance_v34", "ff_forward_match_v28",
    "ff_forward_priority_v32", "ff_forward_recovery_v31", "ff_forward_start_v33",
    "ff_forward_thread_v35", "ff_forward_verify_v27",
}
EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


def now_ts() -> int:
    return int(time.time())


def normalize_key(raw: str) -> bytes:
    try:
        key = base64.urlsafe_b64decode(raw.encode("ascii"))
    except Exception as exc:
        raise RuntimeError("FF_DATA_KEY must be base64") from exc
    if len(key) != 32:
        raise RuntimeError("FF_DATA_KEY must decode to exactly 32 bytes")
    return key


def load_data_key() -> bytes:
    raw = os.getenv("FF_DATA_KEY", "").strip()
    if raw:
        return normalize_key(raw)
    if PRODUCTION:
        raise RuntimeError("FF_DATA_KEY is required in production")
    key_path = ROOT / "data" / ".ff_data_key"
    key_path.parent.mkdir(parents=True, exist_ok=True)
    if key_path.exists():
        return normalize_key(key_path.read_text().strip())
    key = AESGCM.generate_key(bit_length=256)
    key_path.write_text(base64.urlsafe_b64encode(key).decode("ascii"))
    try:
        os.chmod(key_path, 0o600)
    except OSError:
        pass
    return key


DATA_KEY = load_data_key()
AES = AESGCM(DATA_KEY)


def encrypt_json(value: dict[str, str], user_id: int) -> tuple[bytes, bytes]:
    raw = json.dumps(value, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    nonce = secrets.token_bytes(12)
    aad = f"4ever-forward:user:{user_id}:state:v1".encode()
    return nonce, AES.encrypt(nonce, raw, aad)


def decrypt_json(nonce: bytes, ciphertext: bytes, user_id: int) -> dict[str, str]:
    raw = AES.decrypt(nonce, ciphertext, f"4ever-forward:user:{user_id}:state:v1".encode())
    data = json.loads(raw.decode("utf-8"))
    if not isinstance(data, dict):
        raise ValueError("state is not an object")
    return {str(k): str(v) for k, v in data.items()}


def hash_password(password: str, salt: bytes | None = None) -> tuple[bytes, bytes]:
    salt = salt or secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=2**14, r=8, p=1, dklen=32)
    return salt, digest


def verify_password(password: str, salt: bytes, expected: bytes) -> bool:
    _, actual = hash_password(password, salt)
    return hmac.compare_digest(actual, expected)


def sha(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(254), unique=True, index=True)
    password_salt: Mapped[bytes] = mapped_column(LargeBinary)
    password_hash: Mapped[bytes] = mapped_column(LargeBinary)
    role: Mapped[str] = mapped_column(String(32), default="member")
    email_verified_at: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    created_at: Mapped[int] = mapped_column(BigInteger)


class LoginSession(Base):
    __tablename__ = "sessions"
    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    csrf_token: Mapped[str] = mapped_column(String(128))
    expires_at: Mapped[int] = mapped_column(BigInteger, index=True)
    created_at: Mapped[int] = mapped_column(BigInteger)


class JourneyState(Base):
    __tablename__ = "journey_state"
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    version: Mapped[int] = mapped_column(default=0)
    nonce: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    ciphertext: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    updated_at: Mapped[int | None] = mapped_column(BigInteger, nullable=True)


class SyncAudit(Base):
    __tablename__ = "sync_audit"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    event: Mapped[str] = mapped_column(String(64))
    version: Mapped[int | None] = mapped_column(nullable=True)
    created_at: Mapped[int] = mapped_column(BigInteger, index=True)


class EmailToken(Base):
    __tablename__ = "email_tokens"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(32), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    expires_at: Mapped[int] = mapped_column(BigInteger, index=True)
    used_at: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    created_at: Mapped[int] = mapped_column(BigInteger)


class AuthRateEvent(Base):
    __tablename__ = "auth_rate_events"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    key_hash: Mapped[str] = mapped_column(String(64), index=True)
    action: Mapped[str] = mapped_column(String(32), index=True)
    created_at: Mapped[int] = mapped_column(BigInteger, index=True)


engine_kwargs: dict[str, Any] = {"pool_pre_ping": True}
if DATABASE_URL.startswith("sqlite"):
    engine_kwargs["connect_args"] = {"check_same_thread": False}
engine = create_engine(DATABASE_URL, **engine_kwargs)
Base.metadata.create_all(engine)


def db_session() -> Session:
    return Session(engine)


def clean_email(email: str) -> str:
    email = email.strip().lower()
    if not EMAIL_RE.match(email):
        raise HTTPException(400, "Enter a valid email address.")
    return email


def validate_state(state: dict[str, str]) -> dict[str, str]:
    unknown = sorted(set(state) - SYNC_KEYS)
    if unknown:
        raise HTTPException(400, f"State contains non-sync keys: {', '.join(unknown[:5])}")
    clean: dict[str, str] = {}
    for key, val in state.items():
        if not isinstance(val, str):
            raise HTTPException(400, f"State value for {key} must be a string")
        clean[key] = val
    raw = json.dumps(clean, separators=(",", ":"), ensure_ascii=False).encode()
    if len(raw) > MAX_STATE_BYTES:
        raise HTTPException(413, "Journey state is too large.")
    return clean


def client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def rate_limit(session: Session, action: str, identity: str, limit: int, window: int) -> None:
    cutoff = now_ts() - window
    key = sha(f"{action}|{identity}")
    session.execute(delete(AuthRateEvent).where(AuthRateEvent.created_at < now_ts() - 86400))
    count = session.scalar(select(func.count()).select_from(AuthRateEvent).where(
        AuthRateEvent.key_hash == key, AuthRateEvent.action == action, AuthRateEvent.created_at >= cutoff
    )) or 0
    if count >= limit:
        raise HTTPException(429, "Too many attempts. Try again later.")
    session.add(AuthRateEvent(key_hash=key, action=action, created_at=now_ts()))


def create_session(session: Session, user_id: int) -> tuple[str, str]:
    token = secrets.token_urlsafe(32)
    csrf = secrets.token_urlsafe(24)
    ts = now_ts()
    session.add(LoginSession(token_hash=sha(token), user_id=user_id, csrf_token=csrf,
                             expires_at=ts + SESSION_DAYS * 86400, created_at=ts))
    return token, csrf


def set_session_cookie(response: Response, token: str) -> None:
    response.set_cookie(COOKIE_NAME, token, max_age=SESSION_DAYS * 86400, httponly=True,
                        secure=COOKIE_SECURE, samesite="lax", path="/")


def session_row(token: str | None) -> tuple[LoginSession, User] | None:
    if not token:
        return None
    with db_session() as db:
        row = db.execute(select(LoginSession, User).join(User, User.id == LoginSession.user_id).where(
            LoginSession.token_hash == sha(token), LoginSession.expires_at >= now_ts()
        )).first()
        return row if row else None


def require_session(token: str | None) -> tuple[LoginSession, User]:
    row = session_row(token)
    if not row:
        raise HTTPException(401, "Sign in required.")
    return row


def require_csrf(sess: LoginSession, csrf: str | None) -> None:
    if not csrf or not hmac.compare_digest(sess.csrf_token, csrf):
        raise HTTPException(403, "Invalid CSRF token.")


def require_verified(user: User) -> None:
    if not user.email_verified_at:
        raise HTTPException(403, "Verify your email before cloud sync.")


def state_meta(db: Session, user_id: int) -> tuple[int, int | None]:
    row = db.get(JourneyState, user_id)
    return (row.version, row.updated_at) if row else (0, None)


def issue_email_token(db: Session, user_id: int, kind: str, ttl_seconds: int) -> str:
    db.execute(delete(EmailToken).where(EmailToken.user_id == user_id, EmailToken.kind == kind, EmailToken.used_at.is_(None)))
    raw = secrets.token_urlsafe(32)
    db.add(EmailToken(user_id=user_id, kind=kind, token_hash=sha(raw),
                      expires_at=now_ts() + ttl_seconds, created_at=now_ts()))
    return raw


def send_email(to_email: str, subject: str, body: str) -> None:
    host = os.getenv("FF_SMTP_HOST", "").strip()
    if not host:
        if not PRODUCTION and os.getenv("FF_DEV_EMAIL_LOG", "1") == "1":
            print(f"\n--- DEV EMAIL ---\nTo: {to_email}\nSubject: {subject}\n\n{body}\n--- END EMAIL ---\n")
            return
        raise RuntimeError("SMTP is not configured")
    port = int(os.getenv("FF_SMTP_PORT", "587"))
    user = os.getenv("FF_SMTP_USER", "")
    password = os.getenv("FF_SMTP_PASSWORD", "")
    sender = os.getenv("FF_SMTP_FROM", SUPPORT_EMAIL)
    use_tls = os.getenv("FF_SMTP_STARTTLS", "1") == "1"
    msg = EmailMessage()
    msg["From"] = sender
    msg["To"] = to_email
    msg["Subject"] = subject
    msg.set_content(body)
    with smtplib.SMTP(host, port, timeout=15) as smtp:
        if use_tls:
            smtp.starttls()
        if user:
            smtp.login(user, password)
        smtp.send_message(msg)


def send_verification(db: Session, user: User) -> None:
    token = issue_email_token(db, user.id, "verify", 24 * 3600)
    link = f"{public_base_url()}/api/auth/verify?token={token}"
    send_email(user.email, "Verify your 4EVER FORWARD account",
               f"Verify your email to enable secure cloud sync:\n\n{link}\n\nIf you did not create this account, ignore this message.")


def send_reset(db: Session, user: User) -> None:
    token = issue_email_token(db, user.id, "reset", 30 * 60)
    link = f"{public_base_url()}/reset.html?token={token}"
    send_email(user.email, "Reset your 4EVER FORWARD password",
               f"Use this link within 30 minutes to reset your password:\n\n{link}\n\nIf you did not request this, ignore this message.")


class Credentials(BaseModel):
    email: str = Field(min_length=5, max_length=254)
    password: str = Field(min_length=10, max_length=256)


class StatePut(BaseModel):
    base_version: int = Field(ge=0)
    state: dict[str, str]


class EmailOnly(BaseModel):
    email: str = Field(min_length=5, max_length=254)


class ResetPassword(BaseModel):
    token: str = Field(min_length=20, max_length=256)
    password: str = Field(min_length=10, max_length=256)


class DeleteAccount(BaseModel):
    password: str = Field(min_length=10, max_length=256)


app = FastAPI(title="4EVER FORWARD Public Beta Backend", version="0.2.0", docs_url=None if PRODUCTION else "/docs", redoc_url=None)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Permissions-Policy"] = "geolocation=(), camera=(), microphone=(), payment=()"
    response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; font-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
    if COOKIE_SECURE:
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    if request.url.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store"
    return response


@app.get("/api/health")
def health() -> dict[str, Any]:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return {"ok": True, "service": "4EVER FORWARD backend", "version": "0.2.0", "database": "ok"}
    except Exception as exc:
        raise HTTPException(503, "Database unavailable") from exc


@app.post("/api/auth/register")
def register(payload: Credentials, request: Request, response: Response) -> dict[str, Any]:
    email = clean_email(payload.email)
    with db_session() as db:
        rate_limit(db, "register", client_ip(request), 5, 3600)
        salt, digest = hash_password(payload.password)
        user = User(email=email, password_salt=salt, password_hash=digest, role="member", created_at=now_ts())
        db.add(user)
        try:
            db.flush()
        except IntegrityError:
            db.rollback()
            raise HTTPException(409, "An account with that email already exists.")
        db.add(JourneyState(user_id=user.id, version=0))
        token, csrf = create_session(db, user.id)
        db.add(SyncAudit(user_id=user.id, event="account_created", version=0, created_at=now_ts()))
        verification_sent = True
        try:
            send_verification(db, user)
        except Exception:
            # Account creation must not fail just because transactional email is
            # temporarily unavailable or misconfigured. The verification token
            # remains stored so the user can resend verification later.
            verification_sent = False
            db.add(SyncAudit(user_id=user.id, event="verification_email_failed", version=0, created_at=now_ts()))
        db.commit()
        user_id = user.id
    set_session_cookie(response, token)
    message = (
        "Account created. Check your email to verify your account and enable cloud sync."
        if verification_sent else
        "Account created. Verification email could not be sent yet. You can sign in now and resend verification from Account + Sync."
    )
    return {"authenticated": True, "user": {"id": user_id, "email": email, "role": "member", "email_verified": False},
            "csrf": csrf, "state_version": 0, "state_updated_at": None,
            "verification_sent": verification_sent,
            "message": message}


@app.post("/api/auth/login")
def login(payload: Credentials, request: Request, response: Response) -> dict[str, Any]:
    email = clean_email(payload.email)
    with db_session() as db:
        rate_limit(db, "login", f"{client_ip(request)}|{email}", 10, 900)
        user = db.scalar(select(User).where(User.email == email))
        if not user or not verify_password(payload.password, user.password_salt, user.password_hash):
            db.commit()
            raise HTTPException(401, "Email or password is incorrect.")
        token, csrf = create_session(db, user.id)
        version, updated_at = state_meta(db, user.id)
        db.add(SyncAudit(user_id=user.id, event="login", version=version, created_at=now_ts()))
        result_user = {"id": user.id, "email": user.email, "role": user.role, "email_verified": bool(user.email_verified_at)}
        db.commit()
    set_session_cookie(response, token)
    return {"authenticated": True, "user": result_user, "csrf": csrf, "state_version": version, "state_updated_at": updated_at}


@app.post("/api/auth/logout")
def logout(response: Response, ff_session: str | None = Cookie(default=None), x_csrf_token: str | None = Header(default=None)) -> dict[str, bool]:
    sess, user = require_session(ff_session)
    require_csrf(sess, x_csrf_token)
    with db_session() as db:
        db.execute(delete(LoginSession).where(LoginSession.token_hash == sess.token_hash))
        db.add(SyncAudit(user_id=user.id, event="logout", version=None, created_at=now_ts()))
        db.commit()
    response.delete_cookie(COOKIE_NAME, path="/")
    return {"ok": True}


@app.get("/api/auth/me")
def me(ff_session: str | None = Cookie(default=None)) -> dict[str, Any]:
    row = session_row(ff_session)
    if not row:
        return {"authenticated": False}
    sess, user = row
    with db_session() as db:
        version, updated_at = state_meta(db, user.id)
    return {"authenticated": True, "user": {"id": user.id, "email": user.email, "role": user.role,
            "email_verified": bool(user.email_verified_at)}, "csrf": sess.csrf_token,
            "state_version": version, "state_updated_at": updated_at}


@app.post("/api/auth/resend-verification")
def resend_verification(request: Request, ff_session: str | None = Cookie(default=None), x_csrf_token: str | None = Header(default=None)) -> dict[str, bool]:
    sess, user = require_session(ff_session)
    require_csrf(sess, x_csrf_token)
    if user.email_verified_at:
        return {"ok": True}
    with db_session() as db:
        rate_limit(db, "resend", f"{client_ip(request)}|{user.email}", 3, 3600)
        fresh = db.get(User, user.id)
        send_verification(db, fresh)
        db.commit()
    return {"ok": True}


@app.get("/api/auth/verify")
def verify_email(token: str) -> RedirectResponse:
    with db_session() as db:
        et = db.scalar(select(EmailToken).where(EmailToken.token_hash == sha(token), EmailToken.kind == "verify",
                                                EmailToken.used_at.is_(None), EmailToken.expires_at >= now_ts()))
        if not et:
            return RedirectResponse("/?verified=invalid", status_code=303)
        user = db.get(User, et.user_id)
        user.email_verified_at = now_ts()
        et.used_at = now_ts()
        db.add(SyncAudit(user_id=user.id, event="email_verified", version=None, created_at=now_ts()))
        db.commit()
    return RedirectResponse("/?verified=1", status_code=303)


@app.post("/api/auth/request-reset")
def request_reset(payload: EmailOnly, request: Request) -> dict[str, Any]:
    email = clean_email(payload.email)
    with db_session() as db:
        rate_limit(db, "reset_request", f"{client_ip(request)}|{email}", 5, 3600)
        user = db.scalar(select(User).where(User.email == email))
        if user:
            try:
                send_reset(db, user)
            except RuntimeError:
                if PRODUCTION:
                    db.rollback()
                    raise HTTPException(503, "Password reset email service is unavailable.")
        db.commit()
    return {"ok": True, "message": "If that account exists, a reset email has been sent."}


@app.post("/api/auth/reset-password")
def reset_password(payload: ResetPassword, request: Request) -> dict[str, bool]:
    with db_session() as db:
        rate_limit(db, "reset_apply", client_ip(request), 10, 3600)
        et = db.scalar(select(EmailToken).where(EmailToken.token_hash == sha(payload.token), EmailToken.kind == "reset",
                                                EmailToken.used_at.is_(None), EmailToken.expires_at >= now_ts()))
        if not et:
            db.commit()
            raise HTTPException(400, "Reset link is invalid or expired.")
        user = db.get(User, et.user_id)
        salt, digest = hash_password(payload.password)
        user.password_salt, user.password_hash = salt, digest
        et.used_at = now_ts()
        db.execute(delete(LoginSession).where(LoginSession.user_id == user.id))
        db.add(SyncAudit(user_id=user.id, event="password_reset", version=None, created_at=now_ts()))
        db.commit()
    return {"ok": True}


@app.get("/api/state")
def get_state(ff_session: str | None = Cookie(default=None)) -> dict[str, Any]:
    sess, user = require_session(ff_session)
    require_verified(user)
    with db_session() as db:
        state_row = db.get(JourneyState, user.id)
        if not state_row or state_row.version == 0 or not state_row.ciphertext:
            return {"version": 0, "updated_at": None, "state": {}}
        try:
            state = decrypt_json(state_row.nonce, state_row.ciphertext, user.id)
        except Exception as exc:
            raise HTTPException(500, "Stored journey state could not be decrypted.") from exc
        return {"version": state_row.version, "updated_at": state_row.updated_at, "state": state}


@app.put("/api/state")
def put_state(payload: StatePut, ff_session: str | None = Cookie(default=None), x_csrf_token: str | None = Header(default=None)) -> dict[str, Any]:
    sess, user = require_session(ff_session)
    require_csrf(sess, x_csrf_token)
    require_verified(user)
    state = validate_state(payload.state)
    with db_session() as db:
        row = db.get(JourneyState, user.id)
        current_version = row.version if row else 0
        if payload.base_version != current_version:
            raise HTTPException(409, detail={"message": "Server state changed since your last sync.", "server_version": current_version})
        nonce, ciphertext = encrypt_json(state, user.id)
        new_version, ts = current_version + 1, now_ts()
        if not row:
            row = JourneyState(user_id=user.id, version=new_version, nonce=nonce, ciphertext=ciphertext, updated_at=ts)
            db.add(row)
        else:
            row.version, row.nonce, row.ciphertext, row.updated_at = new_version, nonce, ciphertext, ts
        db.add(SyncAudit(user_id=user.id, event="state_saved", version=new_version, created_at=ts))
        db.commit()
    return {"ok": True, "version": new_version, "updated_at": ts, "keys_saved": len(state)}


@app.get("/api/account/export")
def account_export(ff_session: str | None = Cookie(default=None)) -> dict[str, Any]:
    sess, user = require_session(ff_session)
    require_verified(user)
    with db_session() as db:
        row = db.get(JourneyState, user.id)
        state = decrypt_json(row.nonce, row.ciphertext, user.id) if row and row.ciphertext else {}
        audits = db.scalars(select(SyncAudit).where(SyncAudit.user_id == user.id).order_by(SyncAudit.created_at.desc()).limit(100)).all()
        return {"exported_at": now_ts(), "account": {"email": user.email, "created_at": user.created_at,
                "email_verified_at": user.email_verified_at}, "journey_state": state,
                "activity": [{"event": a.event, "version": a.version, "created_at": a.created_at} for a in audits]}


@app.post("/api/account/delete")
def account_delete(payload: DeleteAccount, response: Response, ff_session: str | None = Cookie(default=None), x_csrf_token: str | None = Header(default=None)) -> dict[str, bool]:
    sess, user = require_session(ff_session)
    require_csrf(sess, x_csrf_token)
    if not verify_password(payload.password, user.password_salt, user.password_hash):
        raise HTTPException(401, "Password is incorrect.")
    with db_session() as db:
        db.execute(delete(User).where(User.id == user.id))
        db.commit()
    response.delete_cookie(COOKIE_NAME, path="/")
    return {"ok": True}


@app.get("/")
def index() -> FileResponse:
    return FileResponse(ROOT / "static" / "index.html", media_type="text/html")


@app.get("/{path:path}")
def static_fallback(path: str) -> FileResponse:
    candidate = (ROOT / "static" / path).resolve()
    static_root = (ROOT / "static").resolve()
    if static_root not in candidate.parents or not candidate.is_file():
        raise HTTPException(404)
    return FileResponse(candidate)
