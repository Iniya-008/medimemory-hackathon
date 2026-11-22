# Updating the live MediMemory deployment (Render + Vercel)

This version replaces the old code in the GitHub repo. It is built to work with the
existing Render (backend) and Vercel (frontend) services **without changing their settings**.

## 1. Replace the code in GitHub
1. Open the repo in **GitHub Desktop** (File → Clone repository → `Iniya-008/medimemory-hackathon`).
2. In File Explorer, open the cloned folder and **delete everything except the hidden `.git` folder**
   (the old `backend`, `frontend`, `docs`, `README.md`, `.bat` files, etc.).
   This matters: old files like `backend/app/models.py` must not stay next to the new `backend/app/models/` folder.
3. Copy everything from this zip's `medimemory` folder into the cloned folder.
4. In GitHub Desktop: write a summary ("MediMemory v2: full app"), **Commit to main**, then **Push origin**.
5. Render and Vercel redeploy automatically (Render ~3-5 min, Vercel ~1 min).

## 2. Render (backend). Check these settings
| Setting | Value |
|---|---|
| Root Directory | `backend` |
| Build Command | `pip install -r requirements.txt` |
| Start Command | `uvicorn app.main:app --host 0.0.0.0 --port $PORT` |

On first start the app **creates its tables and the fictional demo patient automatically**.
New tables are prefixed `mm_`, so an existing database with the old tables keeps working and nothing is deleted.

Environment variables (old names still work):
| Key | Needed? | Notes |
|---|---|---|
| `SECRET_KEY` (or `JWT_SECRET_KEY`) | yes | long random string |
| `ELEVENLABS_API_KEY` | for voice | from https://elevenlabs.io/app/settings/api-keys (Text to Speech + Speech to Text permissions) |
| `OPENAI_API_KEY` | optional | nicer, AI-worded answers; without it answers quote the records directly |
| `DATABASE_URL` | optional | Render Postgres URL works as-is; empty = SQLite (demo data reloads after each restart) |
| `CORS_ORIGINS` | optional | your Vercel URL; `*.vercel.app` and `*.onrender.com` are allowed by default |

## 3. Vercel (frontend). Check these settings
| Setting | Value |
|---|---|
| Root Directory | `frontend` |
| Framework | Vite (build `npm run build`, output `dist`) |
| Env `VITE_API_BASE` | `https://medimemory-hackathon.onrender.com` (with or without `/api`) |

`frontend/vercel.json` makes page refreshes work and, if `VITE_API_BASE` is missing, forwards `/api` to the Render backend.
After changing an env var in Vercel, click **Redeploy**.

## 4. Check
- `https://medimemory-hackathon.onrender.com/api/health` → `{"status":"ok", ...}`
- `https://medimemory-hackathon.onrender.com/` → shows `"elevenlabs_configured": true` once the key is set
- Open the Vercel site → **Log in as demo patient** (`demo@medimemory.app` / `Demo@1234`)
