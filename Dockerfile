# Use Python 3.11 slim image for smaller size
FROM python:3.11-slim-bookworm

# Env
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Create non-root user
RUN groupadd --gid 1000 appuser && \
    useradd --uid 1000 --gid 1000 --create-home --shell /bin/bash appuser

# System deps for Playwright/Puppeteer
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl wget ca-certificates gnupg \
    libnss3 libnspr4 libdbus-1-3 libatk1.0-0 libatk-bridge2.0-0 libatspi2.0-0 \
    libxcomposite1 libxdamage1 libxfixes3 libxrandr2 libgbm1 libxcb1 libxkbcommon0 \
    libasound2 libgtk-3-0 libgstreamer1.0-0 libgstreamer-plugins-base1.0-0 \
    nodejs npm \
    && rm -rf /var/lib/apt/lists/* && apt-get clean

# Workdir
WORKDIR /app

# Python deps
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir playwright

# Playwright browsers (Chromium + all required OS deps)
RUN playwright install --with-deps chromium

# Puppeteer: install locally in /app and download Chrome
# Note: local install ensures `require('puppeteer')` resolves correctly
RUN npm init -y
RUN npm install puppeteer@21
ENV PUPPETEER_SKIP_DOWNLOAD=false
# Download Chrome revision matching errors you saw (1091)
RUN node -e "require('puppeteer').createBrowserFetcher().download('1091')"

# App code
COPY . .

# Create dirs + permissions
RUN mkdir -p logs exports && \
    chown -R appuser:appuser /app

# Non-root
USER appuser

# Expose port
EXPOSE 10000

# Runtime env
ENV PYTHONPATH=/app \
    HOST=0.0.0.0 \
    PORT=10000 \
    HEADLESS=true

# Healthcheck
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:10000/health || exit 1

# Start
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "10000", "--workers", "1"]
