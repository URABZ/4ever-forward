# 4EVER FORWARD on Replit

## Run
- Use the **Start application** workflow / Run button.
- Command: `bash run_replit.sh`.
- Python 3.12 / FastAPI / Uvicorn serve the existing UI and API together on `0.0.0.0:5000`.
- Dependencies are listed in `requirements.txt`.
- `prepare_static.py` copies only the public files into `static/` and injects the guided-flow script, matching the existing Docker build. Edit the root source files, not the generated copies; restart to refresh them.

## Development data and email
- The app uses its existing SQLite development database in `data/` and generates its existing development encryption key there. Both are excluded from Git. Keep the key with the database or encrypted journey snapshots cannot be decrypted.
- The preview can run without SMTP settings, but real verification and password-reset emails require a configured SMTP provider and a verified `FF_SMTP_FROM` address.
- When SMTP is absent or rejects a message, registration remains unverified and reports the delivery failure; resend returns a clear error. Verification/reset bearer links are never written to workflow logs.
- `run_replit.sh` builds verification links from Replit's HTTPS development domain. A published production deployment needs its own public HTTPS origin.
- Production frame-denial security remains intact. Only Replit development mode permits embedding by Replit's preview.
- `SESSION_SECRET` is not used by this app; its original database-backed session mechanism is unchanged.

## Verification
- Run `python smoke_test.py` for SMTP configuration/TLS handling, registration, token generation/resend/consumption, the verification sync gate, and account export against a temporary database. The SMTP transport is simulated; a real inbox test requires provider credentials and a verified sender.
- `/api/health` checks database connectivity.

## Before a public launch
Development preview is not a production deployment. Follow `LAUNCH_CHECKLIST.md` and `SECURITY_NOTES.md`: configure durable PostgreSQL/backups, a production `FF_DATA_KEY` via Secrets, SMTP delivery, the published public base URL, secure cookies, and a real support contact. Review the draft privacy and terms pages. Do not publish with the development run command.