# 4EVER FORWARD — Account Creation Fix

This build keeps the Simple Flow experience and changes registration so a temporary or misconfigured verification-email service does not block account creation.

- Account creation now completes even if the verification email cannot be sent.
- The user can sign in immediately.
- Cloud sync remains locked until email verification succeeds.
- A failed verification-email attempt is recorded in the audit log without storing the email body or password.
- The user can retry verification from Account + Sync after SMTP is configured.

The transactional email configuration should still be fixed before broad public launch.
