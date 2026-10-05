# 4EVER FORWARD — Public Beta Backend v2

This package is the first **public-beta deployable** backend wrapped around the V35 4EVER FORWARD prototype.

## What changed from Backend v1

- PostgreSQL support through `DATABASE_URL` (SQLite remains available for local development).
- Render Blueprint (`render.yaml`) for a same-origin Docker web service + managed Postgres.
- Database-aware health check at `/api/health`.
- Email verification before cloud journey sync is allowed.
- Password reset with expiring single-use tokens.
- Database-backed auth rate limiting for registration, login, verification resend, and password reset.
- User data export endpoint and in-product download control.
- Server-side account deletion endpoint and in-product control.
- Security headers (CSP, frame denial, nosniff, referrer policy, permissions policy, HSTS in secure mode).
- Existing AES-256-GCM encrypted journey snapshots, HttpOnly sessions, CSRF protection, explicit 20-key sync allow-list, and optimistic version conflicts are preserved.
- Public-beta Privacy & Data and Beta Terms pages are included as **drafts for formal review**.

## Fast deployment shape

The included `render.yaml` defines:

1. `4ever-forward-beta` — Docker/FastAPI web service.
2. `4ever-forward-db` — managed PostgreSQL, private-network only (`ipAllowList: []`).

The web service gets `DATABASE_URL` from the database automatically. Render can generate `FF_DATA_KEY` as a secret. You must provide SMTP settings and a real support email during the first Blueprint setup.

## Required environment values for public beta

- `FF_SUPPORT_EMAIL`
- `FF_SMTP_HOST`
- `FF_SMTP_FROM` — a sender address or domain verified with the SMTP provider

Store `FF_SMTP_USER` and `FF_SMTP_PASSWORD` in Replit Secrets when the provider
requires SMTP authentication. Configure both or leave both empty only if the
provider explicitly permits unauthenticated relay. Do not paste credentials into
chat or commit them to the repository.

Optional:

- `FF_SMTP_PORT` (default 587)
- `FF_SMTP_STARTTLS` (default 1; port 465 uses implicit TLS)
- `FF_PUBLIC_BASE_URL` if a custom public origin is needed. Replit preview uses
  `REPLIT_DEV_DOMAIN`; Render uses `RENDER_EXTERNAL_HOSTNAME`.

## Local run

```bash
cd 4ever-forward-public-beta-v2
python -m pip install -r requirements.txt
./run_local.sh
```

Open `http://127.0.0.1:8000`.

Without SMTP configuration, registration remains unverified, the API reports
that delivery failed, and resend returns an explicit service-unavailable error.
Verification and reset links are never printed to development logs.

## Public-beta launch gate

Before opening registration broadly:

- Put the repo in a private Git provider repository and deploy the Blueprint.
- Confirm HTTPS and the `/api/health` health check.
- Use a paid managed Postgres tier with recovery/backups enabled.
- Configure transactional SMTP and test verification + reset delivery.
- Replace placeholder support contact and complete formal privacy/terms/legal review.
- Test account export and deletion in production.
- Confirm the public beta does **not** request or encourage SSNs, financial credentials, medical records, precise geolocation, or similar unnecessary sensitive identifiers.
- Review resource links and emergency-routing language for the geography being launched.
- Enable application/error monitoring before marketing the beta widely.

## Architecture choice

For speed and security, this beta keeps the UI and API on the **same origin**. That allows HttpOnly cookie sessions and avoids storing bearer tokens in browser JavaScript. The existing V35 browser journey continues to work locally; cloud sync is opt-in and requires email verification.

## Data model boundary

The backend still stores the 20 approved V35 localStorage namespaces as one encrypted versioned snapshot per user. This is intentional for the beta because it lets us deploy without rewriting all V1–V35 features. After real-world validation, the next backend phase can normalize specific parts (users, resources, commitments, referrals, provider permissions) into relational tables.


## V36 Simple Flow UI

The public landing experience now opens the existing guided resource flow by default and presents it as a full-screen, one-choice-at-a-time experience. Choice screens auto-advance, mobile options are compact two-column grids, and only the strongest resource match is shown first. The full V35/V34 prototype remains available through **Explore full site**. Add `?full=1` to the home URL to skip the guided landing when testing advanced sections.
