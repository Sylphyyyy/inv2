# Password reset setup

Configure these values in the deployment environment before using **Forgot Password?**:

- `ADMIN_EMAIL=ralphparas0305@gmail.com` — assigned to the `admin` account at startup only if its recovery email is blank. A different existing address is not overwritten.
- `PUBLIC_BASE_URL=https://your-site.example` — the public HTTPS origin, with no trailing slash.
- `MAIL_SERVER` and `MAIL_DEFAULT_SENDER` — the SMTP host and sender address.
- `MAIL_PORT=587` for STARTTLS, or `MAIL_PORT=465` for implicit TLS.
- `MAIL_USERNAME` and `MAIL_PASSWORD` — both set for authenticated SMTP; both may be omitted for an unauthenticated relay.

Keep mail credentials in the deployment's secret/environment settings, not in source control. Existing databases are migrated at startup. Reset links are single-use and expire after one hour.
