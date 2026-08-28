# SCICS — Docker Runbook

Simple step-by-step guide for running SCICS in Docker.

---

## Prerequisites

**On the machine that will run Docker:**

1. **Docker Desktop installed** — download from https://www.docker.com/products/docker-desktop/
2. **Docker Desktop is running** (system tray shows the whale icon and says "Docker Desktop is running")
3. **~5 GB free disk space** — the SCICS image is ~2–3 GB, plus some working space
4. **Working internet connection** — needed for the first build (downloads pip packages and spaCy models)

Verify Docker is ready:
```bash
docker --version
docker compose version
docker run hello-world
```
If `hello-world` prints a friendly welcome message, Docker is working.

---

## Step 1 — Clone the repo

```bash
git clone https://github.com/areeshaashfaq/SCICS.git
cd SCICS
```

Or if you already have it:
```bash
cd SCICS
git pull
```

---

## Step 2 — Create the `.env` file

Docker needs the database credentials. The `.env` file is **not** in git for security reasons — you have to create it yourself.

In the SCICS root folder, create a file named exactly `.env` with this content:

```
DATABASE_URL=postgresql://<user>:<password>@<host>:<port>/<dbname>
```

Replace with the actual Supabase connection string (get it from Hafsa or Areesha).

Example:
```
DATABASE_URL=postgresql://postgres.abcxyz:mySecretPass123@aws-0-ap-south-1.pooler.supabase.com:6543/postgres
```

**Verify the file exists:**
```bash
ls -la .env
```

If you see the file listed, you're good.

---

## Step 3 — Build the image

```bash
docker compose build
```

**What happens:**
- Downloads Python 3.10 base image (~150 MB, one-time)
- Installs system packages (~2 min)
- Runs `pip install -r requirements.txt` — this installs FastAPI, scispaCy, medspaCy, and the clinical NER model (~5–10 min, mostly downloading)
- Downloads the general spaCy English model (~1 min)
- Copies your code into the image (~10 sec)

**Expected total time: 10–15 minutes** on the first build. Subsequent builds after code changes take under 30 seconds because Docker caches everything up to Layer 3.

**If it fails**, screenshot the last 20-30 lines and send to Hafsa. Docker errors are usually very specific.

---

## Step 4 — Run the container

```bash
docker compose up
```

**What you'll see:**

```
[+] Running 1/0
 ✔ Container scics-api  Created
Attaching to scics-api
scics-api  | INFO:     Started server process [1]
scics-api  | INFO:     Waiting for application startup.
scics-api  | [NLP] Loaded 0 learned synonyms from corrections     ← this line = NLP loaded successfully
scics-api  | INFO:     Application startup complete.
scics-api  | INFO:     Uvicorn running on http://0.0.0.0:8000
```

Once you see "Uvicorn running", the API is live.

**Test it** — open a browser and go to:
```
http://localhost:8000/
```
You should see: `{"message":"Khidmat API is running"}`

And the interactive API docs:
```
http://localhost:8000/docs
```
You should see the Swagger UI with all endpoints (documents, suggestions, chat, corrections, etc.)

---

## Step 5 — Stop the container

Press **Ctrl+C** in the terminal where `docker compose up` is running.

Or from another terminal:
```bash
docker compose down
```

---

## Common commands cheat sheet

| Command | What it does |
|---|---|
| `docker compose build` | Rebuild the image (after code changes) |
| `docker compose up` | Start the container, show logs |
| `docker compose up -d` | Start in background (detached) |
| `docker compose logs -f` | Follow the logs when running detached |
| `docker compose down` | Stop and remove the container |
| `docker compose restart` | Restart the container |
| `docker ps` | List running containers |
| `docker images` | List images on the system |
| `docker system prune` | Clean up unused stuff (frees disk) |

---

## Troubleshooting

### "docker: command not found"
Docker Desktop isn't installed or isn't in your PATH. Restart your terminal after installing.

### "Cannot connect to the Docker daemon"
Docker Desktop isn't running. Start it from the Start menu and wait for the whale icon in the system tray.

### "port is already allocated" / "bind: address already in use"
Something else is using port 8000. Either:
- Stop the other process (probably a uvicorn running elsewhere)
- Or change the port mapping in `docker-compose.yml` from `"8000:8000"` to `"8001:8000"` and use `localhost:8001` instead

### "pull access denied" / network errors during build
Check internet connection. Corporate firewalls sometimes block Docker Hub — try a different network.

### Build fails on `pip install`
Screenshot the error and send to Hafsa. Common cause: a package needs a system library not installed. Fix goes in the Dockerfile.

### Container starts but crashes immediately
Run with logs visible:
```bash
docker compose up
```
Look for the error line, screenshot, send to Hafsa.

### "No such file or directory: .env"
You skipped Step 2. Create the `.env` file.

### DATABASE_URL errors when API starts
Your `.env` has a wrong or old connection string. Get the latest from the team.

---

## What runs where

Important to understand:

- **The API (FastAPI + NLP pipeline)** runs inside Docker on port 8000
- **The database (Supabase PostgreSQL)** runs in the cloud — the container talks to it via the DATABASE_URL
- **The desktop UI (PyQt6)** does NOT run in Docker — it's a Windows app that runs on the coder's machine directly, and connects to the API at http://localhost:8000 (or wherever the API is deployed)

So the workflow to test end-to-end is:
1. Start the API container: `docker compose up`
2. In a separate terminal, launch the desktop app: `python UI/ui_main.py`
3. The desktop app hits the API on localhost:8000

---

## Rebuilding after code changes

If you edit any Python file:
```bash
docker compose down
docker compose up --build
```

The `--build` flag forces a rebuild. Layer caching makes this fast (usually under 30 seconds) unless you changed `requirements.txt`.

---

## For SIUT deployment later

The same `docker compose up` command works on SIUT's server. The differences will be:
- SIUT provides a server with 16+ GB RAM
- The `.env` DATABASE_URL points to a local PostgreSQL on SIUT's network (not Supabase)
- The container runs 24/7 (`docker compose up -d`)
- Coders' desktop apps point their API URL to the SIUT server IP instead of localhost

Nothing else changes.

---

## Contact if stuck

**Hafsa Ehsan** — NLP pipeline, Dockerfile questions
**Areesha Ashfaq** — Backend API, database, UI

Screenshot any error and share it with a message describing what step you were on.
