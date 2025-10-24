FROM python:3.11-slim-bookworm

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    TZ=Asia/Kolkata \
    DEBIAN_FRONTEND=noninteractive

RUN groupadd --gid 1000 appuser && \
    useradd --uid 1000 --gid 1000 --create-home --shell /bin/bash appuser

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl wget ca-certificates gnupg tzdata \
    fonts-noto fonts-noto-color-emoji fonts-liberation fonts-dejavu-core \
    libnss3 libnspr4 libdbus-1-3 libatk1.0-0 libatk-bridge2.0-0 libatspi2.0-0 \
    libx11-xcb1 libxcomposite1 libxdamage1 libxfixes3 libxrandr2 libgbm1 \
    libxcb1 libxkbcommon0 libasound2 libcairo2 libpango-1.0-0 libpangocairo-1.0-0 \
    libgtk-3-0 libgstreamer1.0-0 libgstreamer-plugins-base1.0-0 libxss1 \
    libgconf-2-4 libxtst6 libdrm2 libxcursor1 libxi6 \
    && rm -rf /var/lib/apt/lists/* && apt-get clean && apt-get autoremove -y

RUN ln -sf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install playwright and browsers as appuser to avoid permission issues
RUN chown -R appuser:appuser /app

USER appuser

# Install playwright browsers in user directory
RUN playwright install --with-deps chromium

# Switch back to root to copy files and set permissions
USER root

COPY . .

RUN mkdir -p logs exports /tmp/chrome-user-data && \
    chown -R appuser:appuser /app /tmp/chrome-user-data && \
    chmod -R 755 /app /tmp/chrome-user-data

USER appuser

EXPOSE ${PORT:-10000}

ENV PYTHONPATH=/app \
    HOST=0.0.0.0 \
    PORT=${PORT:-10000} \
    HEADLESS=true \
    PLAYWRIGHT_BROWSERS_PATH=/home/appuser/.cache/ms-playwright

HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl --fail http://localhost:${PORT:-10000}/health || exit 1

CMD uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-10000} --workers 1
