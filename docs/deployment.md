# Deploying DocuMind for free

The production setup costs nothing on free tiers:

| Piece | Service | Free tier (late 2026) |
|---|---|---|
| API and ingestion worker | Hugging Face Spaces (Docker, CPU basic) | 2 vCPU, 16 GB RAM; sleeps after 48 h without visitors |
| Database | Neon (PostgreSQL 17 + pgvector) | 1 GB storage, 100 compute-hours a month, scales to zero |
| Cache, rate limits, revoked tokens | Upstash Redis | 500K commands a month |
| Uploaded files and backups | Cloudflare R2 | 10 GB, no download fees (asks for a card, charges $0 under the limits) |
| Frontend | GitHub Pages | Static hosting |
| LLM | Groq | Rate-limited free tier |
| Errors (optional) | Sentry | Developer plan |

GitHub Actions does the rest: `deploy-space.yml` ships the API after CI passes on `main`, `deploy-frontend.yml` builds the site against it, `backup.yml` backs the database up nightly and test-restores it monthly. Each workflow does nothing until its settings exist, so nothing breaks before you finish.

## 1. Create the services

1. **Neon**: create a project on PostgreSQL 17 in the region closest to you. From *Connect*, copy two connection strings: the **pooled** one (host contains `-pooler`) and the **direct** one (untick *Connection pooling*). The migrations enable pgvector themselves.
2. **Upstash**: create a Redis database (free). Copy the `rediss://…` URL.
3. **Cloudflare R2**: create two buckets, `documind` (uploads) and `documind-backups`. Under *Manage R2 API tokens*, create a token with *Object Read & Write* on both. Copy the access key ID, secret, and the S3 endpoint (`https://<account-id>.r2.cloudflarestorage.com`).
4. **Groq**: create an API key at console.groq.com.
5. **Hugging Face**: create a new Space, SDK *Docker*, hardware *CPU basic*, visibility of your choice. Then create an access token with *Write* permission under *Settings → Access Tokens*.
6. Generate the app secret: `python -c "import secrets; print(secrets.token_urlsafe(48))"`.

## 2. Add them to GitHub

In the repository, *Settings → Secrets and variables → Actions*.

**Secrets**

| Name | Value |
|---|---|
| `HF_TOKEN` | Hugging Face write token |
| `SECRET_KEY` | the generated secret |
| `DATABASE_URL` | Neon **pooled** connection string |
| `MIGRATION_DATABASE_URL` | Neon **direct** connection string |
| `REDIS_URL` | Upstash `rediss://` URL |
| `S3_ENDPOINT_URL`, `S3_ACCESS_KEY_ID`, `S3_SECRET_ACCESS_KEY` | R2 endpoint and token |
| `GROQ_API_KEY` | Groq key |
| `SENTRY_DSN` | optional |
| `BACKUP_DATABASE_URL` | Neon **direct** connection string |
| `BACKUP_S3_ENDPOINT_URL`, `BACKUP_S3_ACCESS_KEY_ID`, `BACKUP_S3_SECRET_ACCESS_KEY` | R2 endpoint and token (the same token works) |

**Variables**

| Name | Value |
|---|---|
| `HF_SPACE` | `<your-hf-username>/<space-name>` |
| `API_URL` | `https://<your-hf-username>-<space-name>.hf.space` |
| `CORS_ORIGINS` | `https://<your-github-username>.github.io` |
| `KEEPALIVE` | optional, `true` to ping the Space twice a day so it never sleeps (check Hugging Face's terms first) |

Under *Settings → Pages*, set *Source* to *GitHub Actions*.

## 3. Deploy

Merge to `main` (or run *Deploy API to Hugging Face Spaces* by hand from the Actions tab). The workflow copies the secrets into the Space, pushes the code, and waits until `/api/health/ready` answers. The first build takes about ten minutes; Hugging Face builds the Docker image, including the frontend and the models.

Then run *Deploy frontend to GitHub Pages*. The site is at `https://<your-github-username>.github.io/<repository>/`; the API also serves the same app at the Space URL.

On first start the app runs the database migrations. Uploads, chunks and the graph go to Neon; files go to R2.

## 4. Check it

- `https://<space-host>/api/health/ready` should report `database`, `redis` and `storage` as `ok`.
- Run the smoke test against it with a throwaway account: `python scripts/smoke_test.py --base https://<space-host> --secret-key <SECRET_KEY>`.
- Run *Database backup* by hand with *restore test* ticked to see a backup restored end to end.

## What to expect

- **Cold starts.** A Space that slept takes up to a minute to start; the site shows "Starting the server…" and retries until it answers. Neon also suspends after 5 idle minutes and resumes in well under a second.
- **Limits.** Defaults: 5 sign-ups an hour per network, 20 questions a minute and 200,000 LLM tokens a day per user, 200 documents and 500 MB per user. All are environment variables (see `backend/.env.example`), set as Space variables.
- **Logs.** Space logs are JSON with a request ID on every line; the same ID is returned to clients in `X-Request-ID`.

## Running elsewhere

The image runs anywhere Docker does. On a single VM, `docker compose up -d` brings up Postgres, Redis, S3-compatible storage and the API together; put a TLS proxy such as Caddy in front and set `TRUST_PROXY_HEADERS=true`.
