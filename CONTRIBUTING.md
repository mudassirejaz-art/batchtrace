# Contributing to BatchTrace

Thank you for helping improve BatchTrace.

## Before you contribute

- Discuss significant product behavior changes in an issue before large refactors.
- Do not commit real customer data, private emails, credentials, database dumps or `.env` files.
- Preserve tenant isolation, role permissions, and independent approval rules.
- Keep CSV observations historical and credit records clearly labelled as **internal**, not verified bank payments.
- Do not change the visual design system without an agreed design reason.

## Development checks

1. Follow [`docs/USER_GUIDE.md`](docs/USER_GUIDE.md) to create a **new isolated local database**.
2. Frontend: `cd frontend && npm ci && npm run build && npm run lint`.
3. Backend: run the 12 standalone smoke scripts only against a specifically designated **disposable** database; these scripts write fixtures.
4. Never run production migrations, alter hosted data or publish secrets as part of a contribution.

Submit a pull request explaining the change, any security implications, and the test evidence. There is no promised review turnaround or maintenance SLA.

By contributing code, you agree it can be distributed under the repository's MIT License. Third-party materials must be appropriately licensed and credited.
