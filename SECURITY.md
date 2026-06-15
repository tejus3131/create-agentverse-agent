
# Security Policy

## Supported Versions

Only the **latest released version** is supported with security updates.

---

## Reporting a Vulnerability

If you discover a security issue, please **do not open a public issue**.

Instead, report it privately via email:

📧 **<hello@tejusgupta.dev>**

Please include:

- Description of the vulnerability
- Steps to reproduce (if applicable)
- Potential impact

I’ll do my best to respond promptly.

---

Thanks for helping keep the project secure.

---

## Generated project secrets

Scaffolded projects write credentials to `.env`:

- `POSTGRES_PASSWORD` and `AGENT_SEED`
- `AGENTVERSE_API_KEY`, Stripe, and Skyfire keys when configured

Never commit `.env` files. Use strong Postgres passwords in production.

`AGENTVERSE.md` is public profile text (not a secret) but may contain PII — treat it like published content.
