# BatchTrace — Free Self-Hosting & User Guide

BatchTrace is **free, open-source software** for inventory expiry tracking, supplier return workflows and **internal** credit reconciliation. This repository includes the source code, not an online account or a hosted service. You can run it locally without buying a domain or a VPS. Running it for others on the public internet requires your own hosting and operational security.

> **Important:** BatchTrace does **not** send returns to suppliers, communicate with banks, prove a supplier issued credit, or automatically recover money. A recorded credit is an **internal evidence record**, not proof that money was paid.

## 1. What you need

- Ubuntu Linux or Ubuntu under Windows WSL (the locally validated environment)
- Python **3.12** and venv, Node.js **22** and npm, PostgreSQL **16**, Git
- Ability to install packages on your own computer
- No local Docker requirement

This guide is for a fresh development/demo installation. It is **not a production deployment runbook**. Do not point these commands at a database containing important data.

## 2. Download the project

```bash
git clone https://github.com/mudassirejaz-art/batchtrace.git
cd batchtrace
```

## 3. Prepare a NEW local PostgreSQL database

These commands are for a new dedicated test environment only. If the role or database already exists, **stop and inspect your setup**; never delete or overwrite existing databases to follow a guide.

```bash
sudo service postgresql start
sudo -u postgres createuser --pwprompt batchtrace_dev
sudo -u postgres createdb -O batchtrace_dev batchtrace_db
```

Choose your own **URL-safe** database password (letters, digits, hyphens, underscores) when prompted. Keep that password private. If your PostgreSQL installation uses a different setup, adapt the commands rather than replacing an existing database.

## 4. Run the FastAPI backend

From the repository root:

```bash
cd backend
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

Create `backend/.env` **locally**, not in Git, with the connection to your new dedicated database. Generate a fresh JWT secret with `python -c 'import secrets; print(secrets.token_urlsafe(48))'` and keep it private.

```dotenv
DATABASE_URL=postgresql+asyncpg://batchtrace_dev:YOUR_URL_SAFE_PASSWORD@127.0.0.1:5432/batchtrace_db
JWT_SECRET=REPLACE_WITH_YOUR_OWN_RANDOM_SECRET
ACCESS_TOKEN_MINUTES=30
APP_ENV=development
CORS_ORIGINS=
```

Before migration, confirm `DATABASE_URL` targets **your new local demo database**. Migration changes that database's schema; it does not initialize a public service.

```bash
alembic upgrade head
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Open `http://127.0.0.1:8000/api/v1/health` to check that the API is reachable. Do not expose development mode to the public internet.

## 5. Run the React frontend

In a **second terminal**, from the repository root:

```bash
cd frontend
npm ci
npm run dev
```

- Landing page: `http://127.0.0.1:5173/`
- Sign in / dashboard: `http://127.0.0.1:5173/app`

The Vite development server proxies `/api` to the local FastAPI server. The backend and frontend must both be running for working dashboard actions.

## 6. First-use walkthrough

Create an account using the application's registration flow, then sign in. Use **sample/demo data only** while learning the workflow.

1. **Choose a workspace.** Memberships and permissions are workspace-specific. Owners, admins, staff and viewers have different access levels.
2. **Add a supplier and product.** You need supplier codes and product SKUs before registering batches or importing observations.
3. **Register a batch/lot** with its label, product, supplier and expiry date. A registered lot is metadata, **not** a confirmed on-hand stock count.
4. **Set a supplier return policy.** Define the before/after-expiry return window and effective date. Policy revisions are preserved rather than silently rewriting the past.
5. **Import a historical stock CSV.** Choose an observation date; preview and validate before committing. This creates historical snapshot rows, **not** live inventory overwrites. The original uploaded CSV file is not archived by BatchTrace, so retain it separately if required.
6. **Review Recovery signals.** The page explains which batches are relevant to supplier return windows and what evidence supports each signal.
7. **Submit a Physical check.** A person verifies the quantity; another authorized person must review it where independent approval is required. Reviewers cannot approve their own protected submissions.
8. **Create and approve a Supplier claim.** Track approval, dispatch and the supplier outcome. These actions record your team's workflow; they do not contact the supplier automatically.
9. **Reconcile internal credit.** Record expected credit terms and receipt evidence; have another eligible reviewer approve it. View recorded and outstanding amounts. An approved entry is **not bank/payment verification**.
10. **Use the Approval inbox and Team members** to handle independent reviews and workspace access.

### CSV example

Save a UTF-8 CSV with a header like this after creating matching supplier, product and lot records:

```csv
product_sku,supplier_code,batch_number,expiry_date,quantity
SKU-EXAMPLE-001,SUP-EXAMPLE-001,LOT-EXAMPLE-001,2026-11-25,20
```

Select the correct **observation date in the UI**, preview the file, fix reported errors and only then commit it. This is illustrative sample data, **not** a real supplier transaction.

## 7. Test and build safely

The backend includes **12 standalone smoke scripts**. They create records in the configured database, so do **not** run them against an important database. For a clean verification environment, use a separate disposable test database. Run from `backend/` with the environment pointing to that explicitly checked test database:

```bash
for name in auth catalog lots return_policies imports recovery   verifications claims settlements login_throttle roles team; do
  PYTHONPATH="$PWD:$PWD/tests" python "tests/smoke_${name}.py" || exit 1
done
```

Frontend quality checks:

```bash
cd frontend
npm run build
npm run lint
```

Local and GitHub CI passing means these checks succeeded; it is not a security certification, production SLA or proof of restored real-world supplier credit.

## 8. Important limitations and data care

- Protect passwords and secrets. Never commit or share `.env` files, exported databases, tokens or actual customer financial evidence.
- Preserve your original inventory CSV files externally if your business requires a copy. BatchTrace persists parsed, dated observations, not the original file archive.
- Use HTTPS, strong independent secrets, restricted network access, verified backups stored off-server and disaster-recovery drills before serving real users.
- The `deployment/` folder provides an **untested-for-live-production** single-VPS Docker/Caddy skeleton. It needs a real server and operational review; Docker is optional for local development.
- The free GitHub repository does **not** provide a free running BatchTrace server. Each user supplies their own installation/hosting resources.
- Third-party dependencies remain subject to their own license terms.

## 9. Troubleshooting

| Problem | Check |
| --- | --- |
| Landing loads but dashboard API fails | Start backend on `127.0.0.1:8000`; confirm Vite proxy and `/api/v1/health` |
| Database connection fails | Start local PostgreSQL; verify your own `DATABASE_URL`, role, DB and password |
| Permissions/approval rejected | Confirm active workspace role and independent reviewer identity; do not bypass checks |
| CSV preview rejects rows | Match product SKU, supplier code, batch number and exact CSV header; use valid dates and positive quantities |
| Build fails | Check Node.js 22, run `npm ci`, then `npm run build` |

For bugs or improvement requests, use the GitHub repository's Issues page, but **never paste secrets or real customer data**. For a security vulnerability, see [`SECURITY.md`](../SECURITY.md).
