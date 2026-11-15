# Deployment guide - GitHub · Neon · Brevo · Render · Vercel · UptimeRobot

Total time ≈ 40 minutes. Everything works on free tiers (see caveats at the end).
**Order matters:** Neon → Brevo → Render → Vercel → back to Render (set `FRONTEND_URL`) → UptimeRobot.

## 0. Prepare
1. Create a GitHub repo and push this folder (`git init && git add . && git commit -m init && git remote add origin … && git push -u origin main`). `.gitignore` already excludes secrets.
2. Generate secrets locally:
   ```bash
   pip install cryptography && python backend/scripts/generate_secrets.py
   ```
   Keep the output (`SECRET_KEY`, `FIELD_ENCRYPTION_KEYS`). **Back up `FIELD_ENCRYPTION_KEYS` in a password manager - without it encrypted fields are unrecoverable.**

## 1. Neon (PostgreSQL)
1. neon.tech → *New project* (region near Render, e.g. Singapore). 2. *Connection details* → copy the **connection string** (keep `?sslmode=require`; the *pooled* host is fine - the app disables prepared statements for pgbouncer).
   It looks like `postgresql://user:pass@ep-xxx-pooler.ap-southeast-1.aws.neon.tech/neondb?sslmode=require`. Tables are created automatically on first start.

## 2. Brevo (e-mails)
1. brevo.com → sign up → *Senders, Domains & Dedicated IPs* → add and **verify a sender e-mail** (or domain).
2. *SMTP & API* → *API keys* → create a key (starts with `xkeysib-`). You need: `BREVO_API_KEY` and `BREVO_SENDER_EMAIL` (the verified sender).

## 3. Render (backend)
1. render.com → *New +* → **Blueprint** → select the repo (uses `render.yaml`), or *Web Service* manually: Root dir `backend`, Build `pip install -r requirements.txt`, Start `uvicorn app.main:app --host 0.0.0.0 --port $PORT --proxy-headers --forwarded-allow-ips="*"`, Health check `/api/health`, env `PYTHON_VERSION=3.12.3`.
2. Set environment variables:

| Variable | Value |
|---|---|
| `ENV` | `production` |
| `DATABASE_URL` | Neon connection string |
| `SECRET_KEY`, `FIELD_ENCRYPTION_KEYS` | from step 0 |
| `FRONTEND_URL` | your Vercel URL (set after step 4, e.g. `https://sanjeevani-ai.vercel.app`) |
| `ADMIN_EMAIL`, `ADMIN_PASSWORD`, `ADMIN_NAME` | **the doctor login** (use a long unique password). More doctors: `ADMIN_ACCOUNTS=[{"email":"a@x.com","password":"…","name":"Dr A"}]` |
| `BREVO_API_KEY`, `BREVO_SENDER_EMAIL` | from step 2 |
| `REQUIRE_EMAIL_VERIFICATION` | `false` first; set `true` after you confirm e-mails arrive |
| `ADMIN_REQUIRE_OTP` | `true` recommended once Brevo works (doctors get an e-mailed code) |

3. Deploy. Open `https://<service>.onrender.com/api/health/deep` → expect `{"status":"ok","database":true,"kb":true,"ml":true}`.
   The first start seeds 1,391 interactions and creates the doctor account(s). To change the doctor password later: edit `ADMIN_PASSWORD` **and** set `ADMIN_SYNC_PASSWORD=true` (then set it back).

## 4. Vercel (frontend)
1. **Edit `frontend/vercel.json`**: replace `YOUR-RENDER-SERVICE.onrender.com` with your Render host, commit and push.
   *(This rewrite makes the browser talk to `/api` on the Vercel domain, so session cookies are first-party - required for iOS Safari.)*
2. vercel.com → *Add New → Project* → import the repo → **Root Directory `frontend`**, Framework *Vite*, Build `npm run build`, Output `dist`. Deploy.
   The `postinstall` script copies the face models into `public/models` (served from your domain).
3. Copy the production URL → Render → set `FRONTEND_URL` (and, for a custom domain or preview URLs, `ALLOWED_ORIGINS=https://a.com,https://b.vercel.app`) → redeploy Render.

## 5. UptimeRobot (keep Render awake)
uptimerobot.com → *Add New Monitor* → HTTP(s) → URL `https://<service>.onrender.com/api/health` → interval **5 minutes**. (`/api/health` does not touch the database, so Neon can still auto-suspend; use `/api/health/deep` only if you want the DB kept warm.)

## 6. Verify
- Visit your Vercel URL on a **phone**: register (allow the camera) → add medicines → run analysis.
- Sign in at `/admin/login` with the doctor credentials → Patients → open the patient → Data → Audit.
- Test password reset e-mail. Check Render logs for errors.

## 7. Optional hardening - PostgreSQL row-level security
App-level isolation is always on. To add database-enforced isolation:
1. In the Neon SQL editor, as the owner: `CREATE ROLE sanjeevani_app LOGIN PASSWORD '…' NOSUPERUSER NOBYPASSRLS; GRANT ALL ON DATABASE neondb TO sanjeevani_app; GRANT ALL ON SCHEMA public TO sanjeevani_app;` (if tables already exist: `REASSIGN OWNED BY neondb_owner TO sanjeevani_app;`).
2. Put that role in `DATABASE_URL`, check `select rolbypassrls from pg_roles where rolname = current_user;` returns **f**, then set `ENABLE_RLS=true` and redeploy. (Neon’s default owner role may have BYPASSRLS, which would silently disable RLS - hence the dedicated role. This was verified on local PostgreSQL 16; I could not test it on Neon itself.)

## Free-tier caveats
- Render free: spins down after 15 min idle (UptimeRobot prevents this), 512 MB RAM (measured ≈ 230 MB idle with the model loaded), ~1 min cold deploys.
- Neon free: compute auto-suspends; the first query after idle takes ~1 s (handled by `pool_pre_ping`).
- Vercel rewrites to an external origin: keep request bodies < 4.5 MB (the app caps uploads at 3 MB).
- In-memory rate limiting is per instance - fine for one Render instance; use Redis if you scale out.

## Troubleshooting
| Symptom | Fix |
|---|---|
| `403 Origin not allowed` on login | `FRONTEND_URL` / `ALLOWED_ORIGINS` must exactly match the browser origin (no trailing slash) |
| Signed out immediately / cookie missing | You are calling Render directly. Use the Vercel URL; confirm the `vercel.json` rewrite host |
| Camera says “needs HTTPS” | Open the Vercel https URL (not http / not a LAN IP) |
| Face login rejects the real user | Raise `FACE_MATCH_THRESHOLD` to `0.55`; re-enrol in good light |
| No e-mails | Sender not verified in Brevo / wrong key; check Render logs (`[email disabled]` means no key) |
| `Missing required production settings` | Set `SECRET_KEY` and `FIELD_ENCRYPTION_KEYS` |
| Can’t log in as doctor | Check `ADMIN_EMAIL`/`ADMIN_PASSWORD`; the e-mail must not already be a patient account |

## Before real patients
Get a clinical pharmacist to review the knowledge base, add a privacy policy and terms, define data-retention and breach procedures, enable backups on Neon, turn on `REQUIRE_EMAIL_VERIFICATION` and `ADMIN_REQUIRE_OTP`, and check the legal/regulatory position (DPDP Act 2023, and CDSCO software-as-medical-device rules if you make clinical claims).
