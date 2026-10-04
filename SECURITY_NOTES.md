# Security notes — Public Beta Backend v2

## Implemented

- Passwords: Python `scrypt` with unique random salts.
- Sessions: random opaque tokens; only SHA-256 hashes stored server-side; browser cookie is HttpOnly, SameSite=Lax, Secure in production.
- CSRF: per-session CSRF token required for authenticated writes.
- Journey encryption: AES-256-GCM before database storage, with per-user authenticated associated data.
- Sync scope: explicit 20-key allow-list; unrelated browser storage is rejected server-side.
- Concurrency: optimistic state versions prevent stale-device silent overwrite.
- Email verification: cloud journey sync is unavailable until the email is verified.
- Password recovery: expiring, single-use reset tokens; successful reset revokes all sessions.
- Auth abuse controls: database-backed attempt windows for account, login, resend, and reset endpoints.
- User controls: account export and deletion.
- Security headers: CSP, frame denial, nosniff, referrer policy, permissions policy, and HSTS when secure cookies are enabled.
- Production docs endpoints disabled.
- Health endpoint checks database connectivity.

## Still required operationally

- Use HTTPS only and keep `FF_COOKIE_SECURE=1`.
- Keep `FF_DATA_KEY`, SMTP credentials, and database credentials in platform secret management.
- Establish a key rotation and encrypted backup restore procedure. Do **not** rotate `FF_DATA_KEY` without a data re-encryption migration or old snapshots become unreadable.
- Use paid managed Postgres backups/PITR for public data.
- Add centralized error monitoring, uptime alerting, dependency scanning, and security incident procedures.
- Perform formal privacy/legal review before broad launch, especially as the product expands into health/counseling workflows.
- Perform an independent security review / penetration test before handling high-risk or regulated data.
- Provider accounts and provider access remain disabled until explicit consent/RBAC is designed and reviewed.

## Deliberate public-beta restriction

The beta UI tells users not to enter Social Security numbers, financial credentials, medical records, precise location, or similar sensitive identifiers into free-text fields. This reduces data risk while the product and governance model are still being validated.
