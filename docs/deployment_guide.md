# Trinetra-Forensiq Deployment Guide (Render + Vercel)

This guide provides instructions for deploying the Trinetra-Forensiq application using managed PaaS platforms: **Render** (for the FastAPI backend) and **Vercel** (for the Next.js frontend). This is the recommended approach for ease of use, auto-scaling, and managed SSL.

---

## 1. Deploying the Backend on Render

Render will host the FastAPI Python backend. 

### Step 1: Create a Web Service
1. Sign in to your [Render dashboard](https://dashboard.render.com/).
2. Click **New +** and select **Web Service**.
3. Connect your GitHub repository (`Trinetra-Forensiq`).
4. Give it a name (e.g., `trinetra-backend`).
5. **Language / Runtime:** Render should auto-detect this as a **Docker** environment because of the `Dockerfile` at the root. If it doesn't, ensure the environment is set to Docker. 
   *(Alternatively, you can choose Python and set the Start Command to: `uvicorn backend.api:app --host 0.0.0.0 --port $PORT`)*
6. Choose your instance type (Free tier works, but Starter is recommended for memory-intensive LLM/AI tasks).

### Step 2: Configure Environment Variables
In the Render dashboard, scroll down to **Environment Variables** and add your configuration:

| Key | Value | Notes |
| :--- | :--- | :--- |
| `APP_LOG_LEVEL` | `INFO` | |
| `APP_SECRET` | `(your-secure-random-string)` | Must be a strong, random secret. |
| `GEMINI_API_KEY` | `(your-gemini-key)` | Required for LLM functionality. |
| `GROQ_API_KEY` | `(your-groq-key)` | Required for LLM functionality. |
| `APP_CORS_ORIGINS` | `https://your-vercel-frontend-url.vercel.app` | **Crucial:** Update this once you deploy Vercel so your frontend can communicate with the backend. |

### Step 3: Deploy
Click **Create Web Service**. Render will build the Docker container and deploy it.
Once deployed, note the public URL of your backend (e.g., `https://trinetra-backend.onrender.com`).

---

## 2. Deploying the Frontend on Vercel

Vercel will host the Next.js frontend. Vercel automatically detects Next.js projects and provides edge caching and SSL out of the box.

### Step 1: Create a Vercel Project
1. Sign in to your [Vercel dashboard](https://vercel.com/).
2. Click **Add New...** -> **Project**.
3. Import your GitHub repository (`Trinetra-Forensiq`).
4. **Framework Preset:** Vercel will automatically detect **Next.js**.
5. **Root Directory:** Edit this and select the `frontend` folder (since your Next.js app is inside the `frontend/` directory).

### Step 2: Configure Environment Variables
Expand the **Environment Variables** section and add the following:

| Key | Value | Notes |
| :--- | :--- | :--- |
| `APP_BACKEND_URL` | `https://your-backend-url.onrender.com` | The URL you got from Render in Step 1. |
| `NEXT_PUBLIC_API_URL` | `/api` | Keep this as `/api` so that the Next.js rewrites proxy your requests securely to the backend without CORS issues. |

### Step 3: Deploy
Click **Deploy**. Vercel will build and publish your frontend.
Once completed, Vercel will give you a public URL (e.g., `https://trinetra-forensiq.vercel.app`). 

---

## 3. Finalizing the Connection (CORS)

If you haven't already, go back to your **Render dashboard** for the backend service:
1. Go to **Environment**.
2. Add or update the `APP_CORS_ORIGINS` variable to include your newly generated Vercel URL (e.g., `https://trinetra-forensiq.vercel.app`).
3. Save changes. Render will automatically restart your backend service.

## 4. Verification
Go to your Vercel URL in your browser. The application should load successfully, and API requests to `/api/...` will automatically be proxied securely to your Render backend via Next.js rewrites!

## Troubleshooting
- **Backend takes 50 seconds to respond on the first request:** Render spins down free tier instances after inactivity. To fix this, upgrade to the Starter tier.
- **Frontend shows "Network Error":** Ensure `APP_BACKEND_URL` on Vercel exactly matches your Render URL (no trailing slash). Also, ensure `APP_CORS_ORIGINS` on Render exactly matches your Vercel URL.
