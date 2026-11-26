# Clipora AI — Long Video to Viral Shorts Studio

Clipora AI is a full-stack AI-powered web application that converts videos (up to 20 minutes long) into 5–15 ranked, edited, caption-styled, HD MP4 short clips (`9:16`, `16:9`, `1:1`) with individual and batch ZIP downloads.

## Core Capabilities

- **Validated Video Upload & YouTube Link Import**: Drag-and-drop uploader supporting **MP4, MOV, MKV, and WebM**, or paste a **YouTube URL** (`yt-dlp` import), with live upload/download progress, preview, and `ffprobe` validation enforcing videos **under 20 minutes** (`10–1200s`).
- **Direct Instagram Reel / Video HD Downloader**: Paste any public **Instagram Reel, video, or post URL** (`/reel/`, `/p/`, `/tv/`, `/share/reel/`) to download the original video in the highest available **HD MP4** quality directly—skipping AI short generation—with instant inline playback preview, one-click MP4 download, and recent download history.
- **Studio Authentication**: Built-in **Login / Create Account** page backed by MongoDB (`users`) and signed JWT tokens, plus sidebar navigation across **Dashboard**, **Upload / YouTube**, **Instagram Downloader**, **AI Analysis Process**, **Generated Shorts Gallery**, and **Download Manager**.
- **Real Multimodal AI Analysis Pipeline**:
  - **FFmpeg** audio extraction (`16kHz` mono PCM WAV) & poster/thumbnail generation.
  - **Faster-Whisper** speech-to-text transcription with word-level timestamps and VAD filtering.
  - **PySceneDetect** shot boundary detection (`ContentDetector`) + **OpenCV** motion, sharpness, and speaker face-center tracking.
  - **Audio Dynamics Engine** (`SciPy` + `NumPy`) analyzing RMS energy, spectral flux, zero-crossing rate, and excitement peaks.
  - **NLP Highlight Engine** (`SentenceTransformer` embeddings, `scikit-learn` TF-IDF topic centrality, `VADER` sentiment arc, and hook detection) classifying **Interesting, Funny, Important, Motivational, Educational, and Engaging** moments.
- **Smart Shorts Ranking & Deduplication**:
  - Generates **5–15 non-overlapping clips**, each **10–20 seconds** long.
  - Snaps strictly to complete sentence/clause boundaries and aligns subtly with scene transitions.
  - Eliminates duplicate moments using temporal non-overlap and semantic embedding similarity.
  - Automatically generates engaging titles and assigns a calibrated **AI Engagement Score (0–100)**.
- **Interactive Shorts Studio Editor**:
  - Live preview with instant aspect ratio framing (`9:16`, `16:9`, `1:1`) and live caption overlay.
  - Fine clip trimming (`start` / `end`), automatic word-aligned caption regeneration, cue-by-cue text & timing editor.
  - Customizable subtitle presets (`Bold Pop`, `Neon Pill`, `Minimal Clean`, `Classic Cinema`), text/accent/background/outline colors, font size, opacity, and position.
- **HD FFmpeg Rendering & ZIP Download Manager**:
  - Renders true **720p** and **1080p** H.264/AAC MP4 files (`-crf 18/20`, `-movflags +faststart`) with burned-in `.ass` subtitles and OpenCV face-centered cropping.
  - Download individual MP4 clips or bundle all project shorts into a single `.zip` archive.

---

## Project Structure

```text
Clipora-AI/
├── backend/
│   ├── app/
│   │   ├── api/                 # FastAPI route modules (health, videos, clips, exports)
│   │   ├── core/                # Config, AsyncMongoClient DB, FFmpeg/FFprobe resolver
│   │   ├── models/              # Pydantic request/response schemas
│   │   ├── services/            # Storage, audio, Faster-Whisper, PySceneDetect, NLP, ranking, FFmpeg render
│   │   └── main.py              # FastAPI app factory & lifespan
│   ├── tests/                   # Pytest validation, real AI pipeline & FFmpeg export tests
│   ├── pyproject.toml
│   ├── requirements.txt
│   └── .env.example
├── frontend/
│   ├── src/
│   │   ├── api/                 # Typed REST, XHR progress upload, and SSE stream helpers
│   │   ├── components/          # AppShell, DropZoneUploader, ClipPreviewPlayer, Editor tools
│   │   ├── pages/               # Landing, Dashboard, Upload, Processing, Gallery, Editor, Downloads
│   │   └── types/               # TypeScript domain interfaces
│   ├── package.json
│   └── vite.config.ts
├── scripts/
│   ├── start-dev.ps1
│   └── start-dev.sh
└── docker-compose.yml
```

---

## Prerequisites

- **Python** `>= 3.11` (verified on Python `3.14`)
- **Node.js** `>= 20` & **npm**
- **MongoDB** `7.0+` or `8.0+` running on `localhost:27017` (or via Docker)
- **FFmpeg & FFprobe**: System `ffmpeg`/`ffprobe` on `PATH` (recommended), or automatically supplied by the `static-ffmpeg` Python dependency.

---

## Installation & Setup

### 1. Clone the Repository

```bash
git clone <your-repo-url>
cd Clipora-AI
```

### 2. Configure Environment Files

```bash
# Windows PowerShell
Copy-Item backend\.env.example backend\.env
Copy-Item frontend\.env.example frontend\.env
```

```bash
# macOS / Linux
cp backend/.env.example backend/.env
cp frontend/.env.example frontend/.env
```

Default upload duration enforcement in `backend/.env` is `MIN_VIDEO_DURATION_SECONDS=10` (10 seconds) and `MAX_VIDEO_DURATION_SECONDS=1200` (20 minutes).

### 3. Install Backend Dependencies

Using `uv` (recommended):

```bash
cd backend
uv venv .venv
# Windows:
.venv\Scripts\activate
# macOS / Linux:
source .venv/bin/activate

uv pip install -r requirements.txt
```

Or with standard `python -m venv` + `pip`:

```bash
cd backend
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
```

> **Note on AI Models**: On first execution, `Faster-Whisper` (`base` by default) and `sentence-transformers/all-MiniLM-L6-v2` automatically download model weights into your local HuggingFace cache.

### 4. Install Frontend Dependencies

```bash
cd frontend
npm install
```

### 5. How to Run the Application

#### Option A: One-Command Launcher (Recommended on Windows)

If you already set up `backend/.venv` and `frontend/node_modules`, run from the repository root:

```powershell
.\scripts\start-dev.ps1
```

This script automatically:
1. Creates `backend/.env` and `frontend/.env` from `.env.example` if missing.
2. Starts local MongoDB on `127.0.0.1:27017` (creating `.mongod_data/` if port `27017` is not already active).
3. Launches the FastAPI backend on `http://localhost:8000`.
4. Launches the Vite React frontend on `http://localhost:5173`.

On **macOS / Linux**, ensure MongoDB is running and run:

```bash
chmod +x scripts/start-dev.sh
./scripts/start-dev.sh
```

#### Option B: Manual Startup (3 Terminals)

1. **Terminal 1 — Start MongoDB** (skip if MongoDB service is already running):
   ```powershell
   # Windows PowerShell
   New-Item -ItemType Directory -Force -Path .\.mongod_data | Out-Null
   & "C:\Program Files\MongoDB\Server\8.3\bin\mongod.exe" --dbpath .\.mongod_data --port 27017 --bind_ip 127.0.0.1
   ```
   ```bash
   # macOS / Linux
   mkdir -p ./data/db
   mongod --dbpath ./data/db --port 27017
   ```

2. **Terminal 2 — Start FastAPI Backend**:
   ```powershell
   # Windows PowerShell
   cd backend
   .venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
   ```
   ```bash
   # macOS / Linux
   cd backend
   .venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
   ```

3. **Terminal 3 — Start React Vite Frontend**:
   ```bash
   cd frontend
   npm run dev
   ```

#### Option C: Docker Compose

> **Tip for Windows users**: Local `.\scripts\start-dev.ps1` starts in seconds using the already-installed local `MongoDB`, `.venv`, and `node_modules`. Use Docker Compose only when you want containerized services.

```bash
docker compose up --build
```

#### Access URLs

- **Web App UI**: http://localhost:5173
- **API Swagger Docs**: http://localhost:8000/docs
- **System Health Check**: http://localhost:8000/api/health (verifies MongoDB, FFmpeg, FFprobe, Faster-Whisper, PySceneDetect, OpenCV, and NLP models)

---

## Using Clipora AI (Step-by-Step)

1. Open **http://localhost:5173** and click **Create Shorts** (or go to **Upload / YouTube**).
2. Drag and drop a video **under 20 minutes** in **MP4, MOV, MKV, or WebM** format (or paste a YouTube link), adjust target shorts count (`5–15`), aspect ratio (`9:16`, `16:9`, `1:1`), and quality (`720p` / `1080p`), then click **Upload & Start AI Analysis**.
   - **To download an Instagram Reel/video directly without making shorts**: Open **Instagram Downloader** in the sidebar (or switch to the **Instagram Reel / Video** tab on the Upload page), paste the Instagram URL, and click **Fetch & Download HD** to save the high-quality MP4 immediately.
3. Monitor real-time pipeline stages on the **AI Processing** page (Audio extraction -> Faster-Whisper transcription -> PySceneDetect & OpenCV -> Acoustic energy -> NLP ranking -> Clip generation -> FFmpeg HD rendering).
4. Browse and filter clips in the **Generated Shorts Gallery** (`Interesting`, `Funny`, `Important`, `Motivational`, `Educational`, `Engaging`).
5. Click **Edit** on any short to trim start/end bounds, toggle or regenerate auto-captions, edit subtitle cues and colors/presets, switch aspect ratios, and render **720p** / **1080p** MP4s.
6. Open **Download Manager** to download individual HD MP4 clips or package all generated shorts into one `.zip` file.

### Configuration & Troubleshooting Tips

- **Database unavailable (`503`)**: Make sure MongoDB is running on `localhost:27017` before uploading or listing projects.
- **First-run Faster-Whisper speed**: Default `WHISPER_MODEL_SIZE=base` in `backend/.env` downloads model weights once on first transcription. Set `WHISPER_MODEL_SIZE=tiny` for faster CPU processing or `small` for higher accuracy.
- **Video duration rule**: By default, videos up to **20 minutes** (`MAX_VIDEO_DURATION_SECONDS=1200`, minimum `10s`) are accepted. Adjust `MIN_VIDEO_DURATION_SECONDS` / `MAX_VIDEO_DURATION_SECONDS` in `backend/.env` if needed and restart the backend.

---

## Running Verification Tests

```bash
# Windows: .venv\Scripts\python.exe -m pytest -v
# macOS/Linux: .venv/bin/python -m pytest -v
cd backend
.venv\Scripts\python.exe -m pytest -v
```

```bash
cd frontend
npm run build
```

---

## How to Deploy (Production)

Because Clipora AI runs real ML models (`Faster-Whisper`, `SentenceTransformers`, `PySceneDetect`, `OpenCV`) and `FFmpeg` rendering, choose a server or container host with at least **2–4 GB RAM** (4 GB+ recommended for `base`/`small` Whisper models) and persistent disk storage.

### Option 1: Production VPS / Cloud VM with Docker + Nginx (Recommended)

Works on **AWS EC2, DigitalOcean Droplet, Hetzner, Linode, or Azure VM** (Ubuntu 22.04/24.04 with Docker installed).

1. **Clone the repo on your server**:
   ```bash
   git clone <your-repo-url>
   cd Clipora-AI
   ```

2. **Create a root `.env` file with production secrets**:
   ```bash
   cat << 'EOF' > .env
   AUTH_SECRET_KEY=$(openssl rand -hex 32)
   CORS_ORIGINS=https://your-domain.com,http://your-server-ip
   WHISPER_MODEL_SIZE=base
   MONGODB_URI=mongodb://mongodb:27017
   MONGODB_DB=clipora_ai
   EOF
   ```

3. **Build and start the production stack** ([docker-compose.prod.yml](docker-compose.prod.yml)):
   ```bash
   docker compose -f docker-compose.prod.yml up -d --build
   ```
   This starts:
   - `mongodb` with persistent `mongo_data` volume and healthcheck
   - `backend` (FastAPI + FFmpeg + Whisper + NLP) with persistent `clipora_storage` and HuggingFace `hf_cache` volumes
   - `frontend` ([frontend/Dockerfile.prod](frontend/Dockerfile.prod) + [frontend/nginx.conf](frontend/nginx.conf)) serving the compiled React static bundle on port `80` with `2048M` upload limit and unbuffered SSE proxy for `/api/`

4. **Enable HTTPS (SSL)**:
   Put **Caddy**, **Certbot + host Nginx**, or **Cloudflare Proxy** in front of port `80` for automatic Let's Encrypt TLS certificates, and ensure your domain is listed in `CORS_ORIGINS`.

5. **Verify deployment**:
   ```bash
   docker compose -f docker-compose.prod.yml ps
   curl https://your-domain.com/api/health
   ```

---

### Option 2: Deploy on Render (Backend + Frontend + MongoDB Atlas)

Render does not host MongoDB natively, so pair **MongoDB Atlas** with two Render services (**Docker Web Service** for FastAPI + **Static Site** for React). You can configure them via the included [render.yaml](render.yaml) Blueprint or manually in the Render Dashboard below.

> **Important Instance Sizing Note**: Render's Free / Starter (`512 MB` RAM) plans are too small for `PyTorch + Faster-Whisper + SentenceTransformers + FFmpeg` and will hit out-of-memory errors. Use **Standard (`2 GB` RAM)** with `WHISPER_MODEL_SIZE=tiny` (or **Pro `4 GB+`** for `WHISPER_MODEL_SIZE=base`) and attach a **Persistent Disk** so uploads, rendered shorts, and model weights persist.

#### Step 1 — Create MongoDB Database (MongoDB Atlas)
1. Create a free M0 cluster on [MongoDB Atlas](https://www.mongodb.com/atlas).
2. In **Database Access**, create a database username & password.
3. In **Network Access**, add `0.0.0.0/0` so Render's dynamic IPs can connect.
4. Copy your connection string (`mongodb+srv://<user>:<password>@cluster0.xxxxx.mongodb.net/?retryWrites=true&w=majority`).

#### Step 2 — Deploy Backend on Render (Web Service)
1. Push your code to GitHub / GitLab.
2. In Render Dashboard, click **New +** → **Web Service** → select your repository.
3. Configure service settings:
   - **Name**: `clipora-ai-backend`
   - **Root Directory**: `backend`
   - **Language / Runtime**: `Docker` (uses [backend/Dockerfile](backend/Dockerfile), automatically binds Render's `$PORT`)
   - **Instance Type**: `Standard` (`2 GB RAM`) or higher
   - **Health Check Path**: `/health`
   - **Start Command**: *(leave blank so Render runs [backend/Dockerfile](backend/Dockerfile)'s `uvicorn ... --port ${PORT:-8000}`)*
4. Under **Disks**, click **Add Disk**:
   - **Name**: `clipora-storage`
   - **Mount Path**: `/app/storage`
   - **Size**: `20 GB` (or larger for heavy video uploads)
5. Under **Environment Variables**, add:
   - `MONGODB_URI` = `<your MongoDB Atlas connection string>`
   - `MONGODB_DB` = `clipora_ai`
   - `STORAGE_DIR` = `/app/storage`
   - `HF_HOME` = `/app/storage/.hf_cache` *(caches Whisper & NLP weights on disk across deploys)*
   - `AUTH_SECRET_KEY` = `<long random secret string>`
   - `WHISPER_MODEL_SIZE` = `tiny` *(recommended on 2 GB RAM; use `base` on 4 GB+)*
   - `MIN_VIDEO_DURATION_SECONDS` = `10`
   - `MAX_VIDEO_DURATION_SECONDS` = `1200`
   - `CORS_ORIGINS` = `http://localhost:5173` *(update in Step 4 after frontend URL is created)*
6. Click **Deploy Web Service**. Once live, copy its URL (e.g. `https://clipora-ai-backend.onrender.com`) and verify `https://clipora-ai-backend.onrender.com/api/health`.

#### Step 3 — Deploy Frontend on Render (Static Site)
1. In Render Dashboard, click **New +** → **Static Site** → select the same repository.
2. Configure static site settings:
   - **Name**: `clipora-ai-frontend`
   - **Root Directory**: `frontend`
   - **Build Command**: `npm install && npm run build`
   - **Publish Directory**: `dist`
3. Under **Environment Variables**, add:
   - `VITE_API_BASE_URL` = `https://clipora-ai-backend.onrender.com` *(your Step 2 backend URL, no trailing slash — must start with `VITE_` and must be saved in Render's **Environment Variables** before building, because `frontend/.env` is gitignored and missing it causes `405` errors on `POST` requests)*
4. Click **Deploy Static Site** (if you add or change `VITE_API_BASE_URL` later, run **Manual Deploy → Clear build cache & deploy** so Vite bakes it into `dist/`).
5. Once created, open **Redirects/Rewrites** in the Static Site settings and add an SPA rewrite rule so direct page refreshes work:
   - **Source**: `/*`
   - **Destination**: `/index.html`
   - **Action**: `Rewrite`

#### Step 4 — Connect CORS & Verify
1. Copy your frontend Render URL (e.g. `https://clipora-ai-frontend.onrender.com`).
2. Go back to `clipora-ai-backend` → **Environment** → update `CORS_ORIGINS` to `https://clipora-ai-frontend.onrender.com` (and redeploy/restart).
3. Open your frontend URL, create an account on the Login page, and test uploading or importing a video!

> **Alternative**: Click **New +** → **Blueprint** in Render and select this repository to import [render.yaml](render.yaml) automatically, then fill in `MONGODB_URI`, `CORS_ORIGINS`, and `VITE_API_BASE_URL`.

---

### Option 3: Split Hosting (Vercel/Netlify Frontend + Railway/Fly.io Backend)

- **Backend**: Deploy `backend/` using [backend/Dockerfile](backend/Dockerfile) with `/app/storage` mounted on a persistent volume and `MONGODB_URI`, `AUTH_SECRET_KEY`, `CORS_ORIGINS` configured.
- **Frontend (Vercel / Netlify)**: Set Root Directory `frontend`, Build Command `npm run build`, Output Directory `dist`, env `VITE_API_BASE_URL=https://your-backend-url` ([frontend/vercel.json](frontend/vercel.json) already configures SPA rewrites).

---

### Production Checklist

- **Replace `AUTH_SECRET_KEY`**: Never deploy with the default development secret.
- **Set strict `CORS_ORIGINS`**: Include your exact HTTPS frontend origin(s).
- **Upload limits & timeouts**: If placing another reverse proxy (Cloudflare/ALB/Nginx) in front of the backend, set max upload body size `>= 2G` and proxy read timeout `>= 3600s` for long AI jobs & HD ZIP renders.
- **Persistent volumes**: Mount `/app/storage` and `/data/db` on persistent storage so uploaded videos, generated shorts, and MongoDB data survive restarts.
