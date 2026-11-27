# Single image: builds the React app, serves it and the API from FastAPI (SERVE_FRONTEND=true)
FROM node:22-alpine AS web
WORKDIR /web
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim
WORKDIR /app/backend
ENV PYTHONUNBUFFERED=1 SERVE_FRONTEND=true FRONTEND_DIST=/app/frontend/dist
COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/app ./app
COPY --from=web /web/dist /app/frontend/dist
RUN useradd -m app && mkdir -p /app/backend/uploads && chown -R app /app
USER app
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/v1/health', timeout=3).read()"
# Run ONE instance (or set RUN_SCHEDULER=true on exactly one) because the scheduler expires holds and sends reminders.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]
