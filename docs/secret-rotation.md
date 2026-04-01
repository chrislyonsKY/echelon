# Secret Rotation

**Last Updated:** 2026-03-29

This document defines the rotation schedule and step-by-step procedures for all secrets and credentials used by Echelon.

---

## Rotation Schedule

| Secret | Rotation Frequency | Requires Restart | Requires Redeployment | Priority |
|--------|-------------------|------------------|-----------------------|----------|
| `POSTGRES_PASSWORD` | Every 90 days | Yes (all containers) | No | Critical |
| `SECRET_KEY` | Every 90 days | Yes (api) | No | Critical |
| `BYOK_ENCRYPTION_KEY` | Every 180 days (with re-encryption) | Yes (api) | No | Critical |
| `GITHUB_CLIENT_SECRET` | Every 180 days | Yes (api) | No | High |
| `GFW_API_TOKEN` | Every 180 days or on suspected compromise | Yes (worker, beat) | No | Medium |
| `NEWSDATA_API_KEY` | Every 180 days | Yes (worker, beat) | No | Medium |
| `NEWSAPI_API_KEY` | Every 180 days | Yes (worker, beat) | No | Medium |
| `GNEWS_API_KEY` | Every 180 days | Yes (worker, beat) | No | Medium |
| `FIRMS_MAP_KEY` | Every 180 days | Yes (worker, beat) | No | Medium |
| `AISSTREAM_API_KEY` | Every 180 days | Yes (worker, beat) | No | Medium |
| `YOUTUBE_API_KEY` | Every 180 days | Yes (worker, beat) | No | Low |
| `RESEND_API_KEY` | Every 180 days | Yes (worker) | No | Medium |
| `FLOWER_USER` / `FLOWER_PASSWORD` | Every 90 days | Yes (flower) | No | Medium |
| `ACLED_API_KEY` (if applicable) | Every 180 days | Yes (worker, beat) | No | Medium |

**"Requires Restart"** means the relevant container(s) must be restarted to pick up the new value from the environment. No code changes or image rebuilds are needed.

**"Requires Redeployment"** would mean a new Docker image build is needed. None of these secrets require redeployment since they are all injected via environment variables.

---

## General Procedure

All rotations follow the same high-level pattern:

1. Generate the new secret value
2. Update the secret in the `.env` file on the DigitalOcean Droplet
3. If the secret is shared between services (e.g., `POSTGRES_PASSWORD`), update it in all locations simultaneously
4. Restart affected containers
5. Verify service health
6. Revoke or invalidate the old secret if the provider supports it

**Never rotate secrets during active ingestion cycles.** Check Flower to confirm no tasks are currently running before proceeding.

---

## Detailed Procedures

### POSTGRES_PASSWORD

The database password is used by the `db`, `api`, `worker`, `beat`, and `flower` containers.

1. Generate a new password:
   ```bash
   python -c "import secrets; print(secrets.token_urlsafe(32))"
   ```

2. Connect to the running database and change the password:
   ```bash
   docker compose exec db psql -U echelon -d echelon -c "ALTER USER echelon WITH PASSWORD 'NEW_PASSWORD_HERE';"
   ```

3. Update `POSTGRES_PASSWORD` in your `.env` file on the Droplet.

4. Restart all containers that connect to the database:
   ```bash
   docker compose restart api worker beat flower
   ```

5. Verify connectivity:
   ```bash
   docker compose exec api python -c "from app.database import engine; print('OK')"
   curl http://localhost/api/health
   ```

**Important:** Steps 2 and 3 must happen in quick succession. The database password change takes effect immediately, so containers using the old password will fail to connect until restarted with the new value.

---

### SECRET_KEY

Used by FastAPI to sign session cookies. Rotating this key invalidates all active user sessions.

1. Generate a new key:
   ```bash
   python -c "import secrets; print(secrets.token_hex(32))"
   ```

2. Update `SECRET_KEY` in your `.env` file on the Droplet.

3. Restart the API container:
   ```bash
   docker compose restart api
   ```

4. Verify: All users will need to re-authenticate via GitHub OAuth. This is expected.

**Plan rotation during low-traffic periods** since all active sessions will be invalidated.

---

### BYOK_ENCRYPTION_KEY

Used to encrypt user BYOK API keys stored in the `users.byok_key_enc` column. Rotation requires re-encrypting all stored keys.

1. Record the current `BYOK_ENCRYPTION_KEY` value (you will need it for re-encryption).

2. Generate a new key:
   ```bash
   python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
   ```

3. Write and run a one-time migration script that:
   - Reads each non-null `byok_key_enc` value from the `users` table
   - Decrypts it using the **old** key
   - Re-encrypts it using the **new** key
   - Updates the row

   Example (run inside the API container):
   ```python
   from cryptography.fernet import Fernet

   old_fernet = Fernet(b"OLD_KEY_HERE")
   new_fernet = Fernet(b"NEW_KEY_HERE")

   # For each user with a stored key:
   plaintext = old_fernet.decrypt(encrypted_value.encode())
   new_encrypted = new_fernet.encrypt(plaintext).decode()
   # Update the row with new_encrypted
   ```

4. Update `BYOK_ENCRYPTION_KEY` in your `.env` file on the Droplet to the new value.

5. Restart the API container:
   ```bash
   docker compose restart api
   ```

6. Verify by testing the copilot with a user who has server-side key storage enabled.

7. Securely delete the old key value from any notes or temporary files.

**Do not skip the re-encryption step.** If you update the key without re-encrypting, all users with server-side stored keys will be unable to use the copilot until they re-enter their API key.

---

### GITHUB_CLIENT_SECRET

Used for the GitHub OAuth authentication flow.

1. Go to https://github.com/settings/developers and select the Echelon OAuth app.

2. Click "Generate a new client secret."

3. Copy the new secret immediately (GitHub only shows it once).

4. Update `GITHUB_CLIENT_SECRET` in your `.env` file on the Droplet.

5. Restart the API container:
   ```bash
   docker compose restart api
   ```

6. Verify by completing a full OAuth login flow: click "Sign In with GitHub" and confirm the callback succeeds.

7. The old secret remains valid until you explicitly delete it in the GitHub developer settings. Delete it after confirming the new secret works.

---

### External API Keys (GFW, NewsData, NewsAPI, GNews, FIRMS, AISStream, YouTube)

All external API keys follow the same pattern. The specific provider dashboard varies.

1. Log into the provider's dashboard and generate a new API key (or rotate the existing one).

   | Provider | Dashboard URL |
   |----------|--------------|
   | GFW | https://globalfishingwatch.org/our-apis/ |
   | NewsData.io | https://newsdata.io/account |
   | NewsAPI | https://newsapi.org/account |
   | GNews | https://gnews.io/dashboard |
   | NASA FIRMS | https://firms.modaps.eosdis.nasa.gov/api/area/ |
   | AISStream | https://aisstream.io/account |
   | YouTube | https://console.cloud.google.com/apis/credentials |

2. Update the corresponding environment variable in your `.env` file on the Droplet:
   - `GFW_API_TOKEN`
   - `NEWSDATA_API_KEY`
   - `NEWSAPI_API_KEY`
   - `GNEWS_API_KEY`
   - `FIRMS_MAP_KEY`
   - `AISSTREAM_API_KEY`
   - `YOUTUBE_API_KEY`

3. Restart the worker and beat containers (these are the containers that call external APIs):
   ```bash
   docker compose restart worker beat
   ```

4. Verify by checking Flower for successful task execution on the next scheduled ingestion cycle. Alternatively, trigger a manual task run and confirm it completes without authentication errors.

5. If the provider supports revoking old keys, do so after confirming the new key works.

---

### RESEND_API_KEY

Used by the alert engine to send email notifications.

1. Log into https://resend.com/api-keys and create a new API key.

2. Update `RESEND_API_KEY` in your `.env` file (or Railway dashboard).

3. Restart the worker container (alert emails are sent from Celery tasks):
   ```bash
   docker compose restart worker
   ```

4. Verify by triggering a test alert and confirming the email is delivered.

5. Delete the old API key in the Resend dashboard.

---

### FLOWER_USER / FLOWER_PASSWORD

Used for HTTP basic auth on the Flower monitoring dashboard.

1. Choose a new username and password.

2. Update `FLOWER_USER` and `FLOWER_PASSWORD` in your `.env` file on the Droplet.

3. Restart the Flower container:
   ```bash
   docker compose restart flower
   ```

4. Verify by navigating to `/flower/` and logging in with the new credentials.

---

## Emergency Rotation (Suspected Compromise)

If any secret is suspected to be compromised:

1. **Rotate immediately** using the procedures above. Do not wait for the scheduled rotation window.

2. **Check logs** for unauthorized access patterns. For API keys, check the provider dashboard for unexpected usage spikes.

3. **Revoke the old value** at the provider immediately after the new value is deployed and verified.

4. **For `POSTGRES_PASSWORD` compromise:** Additionally review database access logs and consider whether data may have been exfiltrated. Check `pg_stat_activity` for unfamiliar connections.

5. **For `SECRET_KEY` compromise:** All sessions are potentially compromised. Rotate the key (which invalidates all sessions) and notify users if warranted.

6. **For `BYOK_ENCRYPTION_KEY` compromise:** Rotate the key with re-encryption and notify affected users that their stored API keys may have been exposed. Advise them to rotate their own API keys at their respective providers.

---

## Audit Trail

After each rotation, record the following in your team's operational log:

- Date and time of rotation
- Which secret was rotated
- Who performed the rotation
- Confirmation that health checks passed after rotation
- Whether the old secret was revoked at the provider

Do not record the actual secret values in the audit log.
