# Payment Service - container image
# Build context: services/payment-service
FROM python:3.13-slim

# No .pyc files, and logs go straight to `docker logs` without buffering
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Run as an unprivileged user, never as root. /data is where the SQLite file lives.
RUN useradd --system --uid 10001 --no-create-home app \
 && mkdir /data \
 && chown app:app /data

WORKDIR /app

# Dependencies first: this layer is cached until requirements.txt changes
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Application code only (see .dockerignore: no .env, no *.db, no virtualenv)
COPY app.py common.py test_app.py ./

# Non-secret defaults; override at run time with -e / compose `environment:`
ENV PORT=8003 \
    DB_PATH=/data/payment.db \
    LOG_LEVEL=info

USER app
EXPOSE 8003

# Healthy = /health answers. Uses Python itself, so no curl is needed in the image.
HEALTHCHECK --interval=10s --timeout=3s --start-period=5s --retries=3 \
  CMD ["python", "-c", "import os,urllib.request; urllib.request.urlopen('http://127.0.0.1:%s/health' % os.environ.get('PORT','8003'), timeout=2)"]

# 0.0.0.0 = listen on all interfaces INSIDE the container (127.0.0.1 would be unreachable
# from the host). `exec` makes uvicorn PID 1 so `docker stop` shuts it down cleanly.
CMD ["sh", "-c", "exec uvicorn app:app --host 0.0.0.0 --port ${PORT} --log-level ${LOG_LEVEL}"]
