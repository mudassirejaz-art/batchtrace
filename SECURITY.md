# Security Policy

BatchTrace is an open-source **development release candidate**, not a certified managed service. Security hardening, external reviews, production monitoring and off-site backup procedures remain the responsibility of each deployment operator.

## Reporting a potential vulnerability

**Do not disclose vulnerabilities, real passwords, tokens, database URLs or customer information in public GitHub Issues.** If private vulnerability reporting is enabled for the repository, use GitHub's private reporting feature. Otherwise, contact the maintainer through a private channel before sharing technical exploit details. A response time or fix date is not guaranteed.

## Deployment safety

- Use unique production secrets, HTTPS, protected database networks and backups outside the deployment host.
- Do not publicly expose the development server, FastAPI docs in development mode, or database port 5432.
- Apply database migrations only after verifying the target and an independent backup; public release does not authorize mutations to anyone's database.
- Credit records are internal and **never** proof of a verified transfer from a bank.
- Avoid uploading customer or business data into bug reports.
