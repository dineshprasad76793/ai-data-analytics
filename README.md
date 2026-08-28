# AI Data Analytics

Production-oriented, mobile-first AI data analyst built with React + TypeScript + Tailwind and FastAPI + pandas/NumPy/SciPy/scikit-learn.

## What works
- CSV, TSV, XLSX, XLS and JSON upload
- Automatic schema/data-quality profiling
- Numeric, categorical, date and boolean detection
- Descriptive statistics, correlations, IQR and Isolation Forest anomalies
- Automatic dashboard chart selection
- Safe natural-language queries mapped to deterministic operations
- AI explanation layer using an OpenAI-compatible Chat Completions API
- Cleaning center for duplicates, whitespace and missing-value strategies
- PDF report and cleaned CSV/XLSX exports
- Demo dataset with trends and outliers
- Responsive mobile/desktop UI
- Temporary server-side storage with automatic expiry

## Run locally

### Backend
```bash
cd backend
python -m venv .venv
# Windows: .venv\\Scripts\\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

### Frontend
```bash
cd frontend
npm install
npm run dev
```

The Vite dev server proxies `/api` to `http://localhost:8000`.

## AI configuration
Copy `.env.example` to `.env` and configure:
- `AI_API_KEY`: provider secret
- `AI_MODEL`: compatible chat model
- `AI_BASE_URL`: provider API base URL

The deterministic analytics engine is the source of truth. The AI receives computed context rather than the complete dataset for ordinary questions.

## Deployment on Render
The included `render.yaml` builds the frontend into `frontend/dist`, installs the Python backend, and runs FastAPI. The backend serves the compiled frontend when `frontend/dist` exists.

For production, set `ALLOWED_ORIGINS` to the exact deployed origin if the frontend/backend are split into separate services. For a same-origin Render deployment, CORS can be omitted.

## Security notes
- File extension and size validation
- Safe parsing only; uploaded files are never executed
- Temporary storage with TTL cleanup
- API secrets only from environment variables
- No arbitrary code generation/execution for user questions
- CORS is explicit for local development

## API
OpenAPI/Swagger is available at `/docs` when the backend is running.

## Limitations
Forecasting is intentionally conservative and only appears when a date dimension and enough aggregated monthly observations exist. Causal claims are not made from correlation alone. Large datasets should be processed server-side; the browser preview is capped by `MAX_ROWS_FOR_BROWSER`.


## Ownership & Copyright

Copyright © 2026 Dinesh.

Owner: Dinesh
Brand: Dinesh.ai

See `LICENSE` for the full license terms.
