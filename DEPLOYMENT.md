# Trinetra-Forensiq Deployment Guide

This guide provides instructions for deploying Trinetra-Forensiq securely using Docker Compose. The configuration is ready for production, including a single Virtual Machine deployment strategy.

## 1. Prerequisites
- A Virtual Machine (e.g., AWS EC2, DigitalOcean Droplet, GCP Compute Engine).
- Docker and Docker Compose installed on the VM.
- A domain name (optional but recommended for HTTPS).

## 2. Environment Configuration
Your `.env` file contains critical secrets and **must never be committed to Git**. It is already listed in `.gitignore`.

1. Copy `.env.example` to `.env`:
   ```bash
   cp .env.example .env
   ```
2. Open `.env` and fill in the required API keys and configure a strong `APP_SECRET`. 

**Note:** For Render or Vercel, you do not upload the `.env` file. You must set these variables in the platform dashboard (Environment Variables section).

## 3. Deploying using Docker Compose
Since the backend and frontend are containerized, you can launch the complete application stack with a single command.

Run this command in the project root:
```bash
docker compose up --build -d
```

- `--build` ensures both Next.js and FastAPI images are freshly built.
- `-d` runs the containers in detached mode (in the background).

## 4. Reverse Proxy & Access
By default, Nginx binds to port `80` (HTTP). 
- Visit `http://your-vm-ip` to access the frontend.
- API requests will automatically be routed to `/api/` by Nginx.

## 5. Deployment on Render/Vercel
- **Frontend (Vercel):** Link your GitHub repository. Vercel will automatically detect Next.js. Set the Environment Variables (`NEXT_PUBLIC_API_URL` pointing to your deployed backend URL).
- **Backend (Render):** Deploy the backend as a "Web Service" using Docker. Link your GitHub repo, select the `Dockerfile`, and configure your environment variables (like `GEMINI_API_KEY`, `APP_SECRET`, etc.).

## 6. Logs & Maintenance
View logs for the services:
```bash
docker compose logs -f backend
docker compose logs -f frontend
```
To bring down the application:
```bash
docker compose down
```
