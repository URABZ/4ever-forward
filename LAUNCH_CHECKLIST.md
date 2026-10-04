# 4EVER FORWARD — Public Beta Launch Checklist

## Infrastructure
- [ ] Private source repository created.
- [ ] Render Blueprint deployed from `render.yaml`.
- [ ] Web service reports healthy at `/api/health`.
- [ ] Paid Postgres database selected so recovery/backups are available.
- [ ] Database public IP access remains blocked unless specifically needed.
- [ ] `FF_DATA_KEY` exists and is backed up securely outside the app container.
- [ ] Custom domain added (optional for first beta) and HTTPS verified.

## Email + accounts
- [ ] Transactional SMTP configured.
- [ ] New-account verification email tested end to end.
- [ ] Password-reset email tested end to end.
- [ ] Login rate-limit behavior tested.
- [ ] Data export downloaded and reviewed.
- [ ] Account deletion tested with a disposable account.

## Privacy + product boundaries
- [ ] Real support email replaces placeholder.
- [ ] Privacy notice reviewed by counsel/privacy professional.
- [ ] Beta terms reviewed.
- [ ] Notice at collection / consent wording reviewed for launch jurisdiction.
- [ ] No SSN, bank credential, medical-record, precise-location, or other unnecessary sensitive-data fields added.
- [ ] Provider access remains off until explicit user permission and RBAC are implemented.

## Reliability
- [ ] Database restore procedure tested.
- [ ] Application error monitoring configured.
- [ ] Uptime alert configured.
- [ ] Dependency/security scanning configured in source repository.
- [ ] One-device and two-device sync-conflict tests repeated in production.

## Pilot release
- [ ] Use a small public-beta cohort first.
- [ ] Publish an easy feedback path.
- [ ] Review failed signups, sync conflicts, and support requests daily during early beta.
- [ ] Freeze major feature additions while launch defects are being fixed.
