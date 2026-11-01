FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN useradd --system --uid 10001 --no-create-home app \
 && mkdir /data \
 && chown app:app /data

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py common.py test_app.py ./

ENV PORT=8002 \
    DB_PATH=/data/notification.db \
    LOG_LEVEL=INFO

USER app
EXPOSE 8002

HEALTHCHECK --interval=10s --timeout=3s --start-period=5s --retries=3 \
  CMD ["python", "-c", "import os,urllib.request; urllib.request.urlopen('http://127.0.0.1:%s/health' % os.environ.get('PORT','8002'), timeout=2)"]

CMD ["sh", "-c", "exec uvicorn app:app --host 0.0.0.0 --port ${PORT} --log-level info"]
