# SparkRail Day-One Deployment Guide

## 1. Architecture Overview & Decoupled Topology

SparkRail uses a strictly decoupled deployment topology:
- **Frontend**: A static Single Page Application (SPA) built with React, Vite, and React Three Fiber. Hostable on any static web host, including **GitHub Pages**, S3/CloudFront, or Nginx.
- **Backend**: A high-performance Python FastAPI service running the optimization engines (CP-SAT/ALNS), canonical topology graph, cryptographic audit chain, and CRIS adapters. Deployed in an isolated, secure enterprise container or VM.

> [!IMPORTANT]
> **GitHub Pages Scope**:
> GitHub Pages hosts *only* the static frontend bundle (`frontend/dist/`). It does not run Python or execute the solver. In offline demo mode, the frontend utilizes deterministic in-memory client mocks; when connected to a backend, it connects via configurable HTTPS/WSS endpoints.

---

## 2. Environment Configuration

### Backend Environment Variables

| Variable | Default Value | Description |
|---|---|---|
| `SPARKRAIL_MODE` | `synthetic` | Plugin mode: `synthetic`, `shadow`, or `live`. |
| `SPARKRAIL_LIVE_ENABLED` | `false` | Non-negotiable safety gate. Must be `true` to allow live CRIS connections. |
| `API_HOST` | `0.0.0.0` | API server listen interface. |
| `API_PORT` | `8000` | API server listen port. |
| `CORS_ORIGINS` | `http://localhost:5173,...` | Comma-separated list of allowed frontend origins. |
| `CRIS_MTLS_CERT_PATH` | *None* | Path to client certificate for CRIS mTLS. |
| `CRIS_MTLS_KEY_PATH` | *None* | Path to private key for CRIS mTLS. |
| `CRIS_CA_BUNDLE` | *None* | Path to trusted CRIS Root CA bundle. |

### Frontend Environment Variables (`.env.production`)

| Variable | Default Value | Description |
|---|---|---|
| `VITE_BASE_PATH` | `./` | Relative asset path for GitHub Pages subpath deployment. |
| `VITE_API_URL` | `http://localhost:8000` | Default backend API base URL (overridable in browser localStorage). |
| `VITE_DEMO_MODE` | `false` | If `true`, enables offline synthetic demo fallback when API is unreachable. |

---

## 3. Step-by-Step Deployment Procedures

### Procedure A: Local Day-One Shadow Mode Deployment

1. **Clone and setup Python virtual environment**:
   ```bash
   git clone https://github.com/chandrasekarc968-cpu/sparkrail.git
   cd sparkrail
   python -m venv .venv
   source .venv/bin/activate  # Or on Windows: .venv\Scripts\activate
   pip install -r requirements.txt
   ```

2. **Generate deterministic synthetic corridor baseline**:
   ```bash
   python -m src.plugin generate-seed --seed 42 --output-dir data/synthetic
   ```

3. **Launch API Gateway in Shadow Mode**:
   ```bash
   export SPARKRAIL_MODE=shadow
   python -m src.plugin run-api --host 127.0.0.1 --port 8000
   ```

4. **Verify Backend Health**:
   ```bash
   curl http://127.0.0.1:8000/api/v1/health
   ```

5. **Build and Serve Static Frontend**:
   ```bash
   cd frontend
   npm ci
   npm run build
   npx serve dist -l 5173
   ```

---

### Procedure B: GitHub Pages Static Deployment

1. In GitHub repository settings, navigate to **Settings > Pages**.
2. Set **Build and deployment source** to **GitHub Actions**.
3. Push to `main` branch or manually trigger the workflow `.github/workflows/deploy-pages.yml`.
4. The workflow will:
   - Run unit and integration tests (`npm test -- --run`).
   - Compile production static bundle with relative base paths (`VITE_BASE_PATH='./'`).
   - Verify artifacts (`dist/index.html` and `dist/404.html`).
   - Deploy to `https://<username>.github.io/<repo>/`.

---

## 4. Operational Rollback & Failsafe Measures

1. **Zero Field Actuation Failsafe**: SparkRail contains no code paths to issue point-machine, breaker, or signal commands. If the service experiences downtime, existing manual block working on Indian Railways continues without interruption.
2. **Audit Verification**:
   ```bash
   python -m src.plugin verify-audit
   ```
   If any audit event hash mismatch is detected, the command exits with code 1 and outputs the exact tampered index.
