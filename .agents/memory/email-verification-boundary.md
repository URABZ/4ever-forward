---
name: Email verification boundary
description: Durable security requirements for email confirmation and cloud-sync access.
---

Email verification is a hard gate: do not auto-verify accounts or allow cloud sync before a valid, unexpired, one-use verification token is confirmed. Never treat writing an email to logs as delivery, and never log bearer links or message bodies.

**Why:** the user explicitly required verification to remain real and cloud sync to stay gated; verification links are authentication credentials.

**How to apply:** preserve the token check and `require_verified` enforcement across registration, resend, and sync changes. Verify failure and success paths without bypassing the confirmation step.