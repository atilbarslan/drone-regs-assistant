# Deploying

The demo runs on two free services in Frankfurt: a [Render](https://render.com) web service
(`render.yaml`) and a [Neon](https://neon.com) Postgres database with pgvector. The free-tier
figures below were read from the providers' documentation in October 2026; they change, so check
the linked pages.

## 1. Neon: database (dashboard)

1. Create a project in **AWS Europe (Frankfurt), `aws-eu-central-1`**
   ([regions](https://neon.com/docs/introduction/regions)), Postgres 17 (the version the app is
   developed and tested on).
2. Under **Connect**, turn **Connection pooling off** and copy the **direct** connection string
   ([connection pooling](https://neon.com/docs/connect/connection-pooling)). Why direct: see
   "Direct or pooled" below.
3. Save it on your computer as `.env.neon`, one line: `DATABASE_URL='<the string>'`, in single
   quotes (the string contains `&`, which the shell would otherwise read). The file is
   ignored by git (`.env.*` in `.gitignore`); check with `git check-ignore .env.neon`.

## 2. Schema and data (from a developer machine)

The schema is created by the app's migrations. The data is **copied** from the local database,
not embedded again: embedding the 746 passages again would use about three quarters of a day's
free embedding requests (each text in a batch counts as one request; 1,000 a day on our account
in October 2026), for vectors that already exist.

```bash
set -a; source .env.neon; set +a          # DATABASE_URL for this shell only; never echo it
export NEON_DATABASE_URL="$DATABASE_URL"
.venv/bin/python -m app.migrate           # 001-003 on Neon; prints only the file names
```

Copy `documents` and `chunks` only (no `request_log`, no `schema_migrations`), data only, with
the Postgres 17 client inside the local container. `pg_dump` leaves out the generated `tsv`
column (Neon computes it again), keeps the chunk ids and sets the id sequence:

```bash
docker compose exec -T -e NEON_DATABASE_URL db sh -c '
  pg_dump -U drone -d drone_regs --data-only --no-owner --no-privileges \
    --table=documents --table=chunks > /tmp/copy.sql &&
  psql "$NEON_DATABASE_URL" --single-transaction -v ON_ERROR_STOP=1 -q -f /tmp/copy.sql;
  rm -f /tmp/copy.sql'
```

Then check the copy without any API call: the same row counts, the same
`md5(string_agg(content_hash || embedding::text, ',' ORDER BY document_id, ordinal))` on both
sides, the HNSW and GIN indexes, and `python -m eval.retrieval --label neon` (with `DATABASE_URL`
pointing at Neon) giving the same passages as the local database for every evaluation question.

Do **not** run `python -m ingest.embed` against Neon: it would embed every passage again.

## 3. Render: web service (dashboard)

1. **New > Blueprint**, choose this repository; Render reads `render.yaml`
   ([Blueprint spec](https://render.com/docs/blueprint-spec)).
2. When asked, enter `DATABASE_URL` (the Neon direct string) and `GEMINI_API_KEY`. These are
   `sync: false` in the Blueprint: Render asks for them only when the Blueprint is created; later
   changes are made under **Environment**.
3. Deploys do not change the database. If a later version adds a migration, run step 2's
   `app.migrate` by hand before deploying it.

What `render.yaml` sets, and why:

| Setting | Why |
|---|---|
| `PYTHON_VERSION=3.12.13` | Same as CI and local development. Render's default for services created after 11 February 2026 is a newer Python ([Python version](https://render.com/docs/python-version)). The environment variable is used rather than a `.python-version` file, so local tools are not affected. |
| `--workers 1` | The request limits are counted in memory. |
| `--no-access-log` | uvicorn's access log writes every client address to the console, which Render keeps. |
| `--no-proxy-headers` | The client address is read from `X-Forwarded-For` counted from the right (`FORWARDED_TRUSTED_HOPS`). uvicorn's own handling needs the proxies' addresses; with `--forwarded-allow-ips='*'` it takes the leftmost value, which a client can write, because Render appends to the header without removing what the client sent. |
| `API_DOCS=false` | No `/docs`, `/redoc` or `/openapi.json` in production. |
| `HSTS=true` | Browsers keep to HTTPS (Render terminates TLS). |
| `FORWARDED_TRUSTED_HOPS=3` | The number of proxies that append to `X-Forwarded-For`, measured on Render on 10 October 2026: a request without the header arrived with 3 values, one with a forged value with 4 (only the number of values was logged, during the measurement only, never the addresses). With 3, a forged header could not get round the per-address limit, and a second network got its own limit. If Render changes its proxies, measure again; with 0 every visitor counts as one address. |

## First request after a quiet period

Both services sleep when unused:

- A free Render web service spins down after **15 minutes** without traffic; the next request
  starts it again, which takes **about a minute**
  ([free instances](https://render.com/docs/free)).
- A Neon compute suspends after **5 minutes** without queries (not configurable on the free
  plan) and resumes **within a few hundred milliseconds**
  ([scale to zero](https://neon.com/docs/introduction/scale-to-zero)). The app's connection pool
  checks each connection before use, so connections closed during the pause are replaced.

Measured on 10 October 2026: after 20 minutes and after about 90 minutes without visitors, the
first `/health` took **32.3 and 32.4 seconds** (32.4 for the first visit of the day too), the
next one 0.1 seconds. Render's own health checks query the database every few seconds while the
service is up, so the Neon compute stays active as long as the Render service does: about 15
minutes after the last visit plus Neon's 5, about 0.08 CU-hours at 0.25 CU. Once Render has
spun down, Neon showed **Idle**; the health checks do not keep either service awake.

## Free-tier limits that matter here (October 2026)

| Service | Limit | Source |
|---|---|---|
| Render web service | 750 free instance hours a month per workspace; one instance; spins down after 15 minutes | [render.com/docs/free](https://render.com/docs/free) |
| Neon | 1 GB storage per project; 100 CU-hours per project a month; scale to zero after 5 minutes, cannot be turned off | [neon.com/docs/introduction/plans](https://neon.com/docs/introduction/plans) |
| Gemini API | gemini-3.5-flash-lite: 15 requests a minute, 500 a day; gemini-embedding-2: 100 a minute, 1,000 a day (each text counts) | our Google AI Studio account page, 6 October 2026 (limits are per project and not published as fixed numbers) |

The app's own limits stay below Gemini's: 3 questions a minute and 20 a day per address, 12 a
minute and 300 a day in total (`app/config.py`).

## Why the service is not kept awake

A pinger that calls the site every few minutes would avoid the half-minute start, but:

- `/health` queries the database, so it would keep the Neon compute awake too. At the smallest
  size, 0.25 CU ([computes](https://neon.com/docs/manage/computes)), a compute active all month
  (about 744 hours) would use about 186 CU-hours, if CU-hours are size times active hours: more
  than the free 100.
- It would need another always-on service to send the pings, and it works against what the free
  tiers are for.

For a portfolio demo with occasional visitors, a slow first visit is the honest trade-off. Note
what the visitor sees: the page itself comes from the sleeping service, so the first visitor sees
only the browser's own loading indicator for about half a minute, not the page's "searching the
sources" state. That state appears only when the page was already open and the service fell
asleep afterwards (15 minutes without a question).

## Direct or pooled database connection

Neon offers a direct connection and a pooled one through PgBouncer in transaction mode. psycopg
prepares a statement automatically once it has run the same query five times (its default
`prepare_threshold`); PgBouncer
supports protocol-level prepared statements, but not SQL `PREPARE`
([connection pooling](https://neon.com/docs/connect/connection-pooling)). With one worker and a
pool of at most five connections, the direct string is enough and avoids that question.
