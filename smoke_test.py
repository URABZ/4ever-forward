"""Exercise verification, resend, delivery failures, and verified sync locally."""

import io
import os
import re
import tempfile
from contextlib import redirect_stdout
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from fastapi.testclient import TestClient

with tempfile.TemporaryDirectory() as d:
    os.environ["DATABASE_URL"] = f"sqlite:///{Path(d) / 'test.sqlite3'}"
    os.environ["FF_ENV"] = "development"
    os.environ["FF_COOKIE_SECURE"] = "0"
    os.environ["FF_PUBLIC_BASE_URL"] = "https://forward.test"
    os.environ.pop("FF_SMTP_HOST", None)
    os.environ.pop("FF_SMTP_FROM", None)

    import app

    # Missing mail configuration must fail explicitly and never print bearer links.
    output = io.StringIO()
    with redirect_stdout(output):
        try:
            app.send_email("recipient@example.test", "Subject", "token=synthetic-test-token")
            raise AssertionError("Missing SMTP settings must not count as successful delivery.")
        except app.EmailDeliveryError as exc:
            assert "FF_SMTP_HOST" in exc.public_message
    assert output.getvalue() == ""

    # Exercise the configured TLS/authentication path with a local SMTP double.
    os.environ.update({
        "FF_SMTP_HOST": "smtp.example.test",
        "FF_SMTP_PORT": "587",
        "FF_SMTP_USER": "smtp-user",
        "FF_SMTP_PASSWORD": "smtp-password",
        "FF_SMTP_FROM": "4EVER FORWARD <no-reply@verified.example.test>",
        "FF_SMTP_STARTTLS": "1",
    })
    smtp_calls = []

    class FakeSMTP:
        def __init__(self, host, port, timeout):
            smtp_calls.append(("connect", host, port, timeout))

        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

        def ehlo(self):
            smtp_calls.append(("ehlo",))

        def starttls(self, context):
            assert context is not None
            smtp_calls.append(("starttls",))

        def login(self, user, password):
            smtp_calls.append(("login", user, password))

        def send_message(self, message):
            smtp_calls.append(("send", message["From"], message["To"], message["Subject"]))

    real_smtp = app.smtplib.SMTP
    app.smtplib.SMTP = FakeSMTP
    try:
        app.send_email("recipient@example.test", "Test", "Test message")
    finally:
        app.smtplib.SMTP = real_smtp
    assert ("starttls",) in smtp_calls
    assert ("login", "smtp-user", "smtp-password") in smtp_calls
    assert ("send", "4EVER FORWARD <no-reply@verified.example.test>",
            "recipient@example.test", "Test") in smtp_calls

    class RejectingSMTP(FakeSMTP):
        def login(self, _user, _password):
            raise app.smtplib.SMTPAuthenticationError(535, b"credentials rejected")

    app.smtplib.SMTP = RejectingSMTP
    try:
        try:
            app.send_email("recipient@example.test", "Test", "Test message")
            raise AssertionError("Provider authentication failures must be surfaced.")
        except app.EmailDeliveryError as exc:
            assert exc.smtp_code == 535
            assert "rejected authentication" in exc.public_message
    finally:
        app.smtplib.SMTP = real_smtp

    # API-level flow: registration creates a hashed token, resend dispatches a
    # fresh message without invalidating prior links, and verification unlocks sync.
    mails = []
    app.send_email = lambda to, subject, body: mails.append((to, subject, body))
    client = TestClient(app.app)
    assert client.get("/api/health").status_code == 200
    registered = client.post("/api/auth/register", json={
        "email": "smoke@example.test", "password": "smoketestpassword123"
    })
    assert registered.status_code == 200
    assert registered.json()["verification_sent"] is True
    csrf = registered.json()["csrf"]
    assert len(mails) == 1

    def parse_verification(body):
        link = next(line for line in body.splitlines() if "/api/auth/verify?" in line)
        parts = urlsplit(link)
        assert parts.scheme == "https"
        assert parts.netloc == "forward.test"
        assert parts.path == "/api/auth/verify"
        token = parse_qs(parts.query)["token"][0]
        assert re.fullmatch(r"[A-Za-z0-9_-]{40,}", token)
        return token, parts

    first_token, first_url = parse_verification(mails[0][2])
    assert mails[0][0] == "smoke@example.test"
    assert mails[0][1] == "Verify your 4EVER FORWARD account"
    with app.db_session() as db:
        first_row = db.scalar(app.select(app.EmailToken).where(
            app.EmailToken.token_hash == app.sha(first_token),
            app.EmailToken.kind == "verify",
        ))
        assert first_row is not None
        assert first_row.used_at is None
        assert first_row.expires_at > app.now_ts()
        assert first_row.token_hash != first_token
        user = db.scalar(app.select(app.User).where(app.User.email == "smoke@example.test"))
        assert user is not None and user.email_verified_at is None

    state = {"4everForwardTasksV2": "[]"}
    assert client.get("/api/state").status_code == 403
    assert client.put("/api/state", json={"base_version": 0, "state": state},
                      headers={"X-CSRF-Token": csrf}).status_code == 403

    resent = client.post("/api/auth/resend-verification", json={},
                         headers={"X-CSRF-Token": csrf})
    assert resent.status_code == 200 and resent.json()["ok"] is True
    assert len(mails) == 2
    second_token, second_url = parse_verification(mails[1][2])
    assert second_token != first_token
    with app.db_session() as db:
        old_row = db.scalar(app.select(app.EmailToken).where(
            app.EmailToken.token_hash == app.sha(first_token),
        ))
        assert old_row is not None and old_row.used_at is not None
    old_after_resend = client.get(f"{first_url.path}?{first_url.query}", follow_redirects=False)
    assert old_after_resend.status_code == 303
    assert old_after_resend.headers["location"] == "/?verified=invalid"

    verified = client.get(f"{second_url.path}?{second_url.query}", follow_redirects=False)
    assert verified.status_code == 303
    assert verified.headers["location"] == "/?verified=1"
    me = client.get("/api/auth/me").json()
    assert me["authenticated"] is True and me["user"]["email_verified"] is True
    assert client.get("/api/state").status_code == 200
    uploaded = client.put("/api/state", json={"base_version": 0, "state": state},
                          headers={"X-CSRF-Token": me["csrf"]})
    assert uploaded.status_code == 200
    assert client.get("/api/account/export").status_code == 200
    old_link = client.get(f"{first_url.path}?{first_url.query}", follow_redirects=False)
    assert old_link.status_code == 303
    assert old_link.headers["location"] == "/?verified=invalid"

    # A provider outage stays visible to the UI; the account and token remain
    # present, resend returns 503, and an older pending token remains usable.
    def failed_delivery(*_):
        raise app.EmailDeliveryError("SMTP test failure.")

    app.send_email = failed_delivery
    failed = client.post("/api/auth/register", json={
        "email": "delivery-failure@example.test", "password": "smoketestpassword456"
    })
    assert failed.status_code == 200
    assert failed.json()["verification_sent"] is False
    assert "SMTP test failure." in failed.json()["message"]
    failed_csrf = failed.json()["csrf"]
    failed_resend = client.post("/api/auth/resend-verification", json={},
                                headers={"X-CSRF-Token": failed_csrf})
    assert failed_resend.status_code == 503
    assert failed_resend.json()["detail"] == "SMTP test failure."
    with app.db_session() as db:
        failed_user = db.scalar(app.select(app.User).where(
            app.User.email == "delivery-failure@example.test"
        ))
        assert failed_user is not None and failed_user.email_verified_at is None
        pending = db.scalars(app.select(app.EmailToken).where(
            app.EmailToken.user_id == failed_user.id,
            app.EmailToken.kind == "verify",
            app.EmailToken.used_at.is_(None),
        )).all()
        assert len(pending) >= 2

    print("smoke test passed: SMTP validation/TLS, hashed verification token, resend, one-time verification, sync gate, delivery failures")