# Use Python 3.11 slim image for smaller size
FROM python:3.11-slim-bookworm

# Environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    TZ=Asia/Kolkata \
    DEBIAN_FRONTEND=noninteractive

# Create non-root user
RUN groupadd --gid 1000 appuser && \
    useradd --uid 1000 --gid 1000 --create-home --shell /bin/bash appuser

# Install system dependencies for Playwright/Chromium
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl wget ca-certificates gnupg tzdata \
    fonts-noto fonts-noto-color-emoji fonts-liberation fonts-dejavu-core \
    libnss3 libnspr4 libdbus-1-3 libatk1.0-0 libatk-bridge2.0-0 libatspi2.0-0 \
    libx11-xcb1 libxcomposite1 libxdamage1 libxfixes3 libxrandr2 libgbm1 \
    libxcb1 libxkbcommon0 libasound2 libcairo2 libpango-1.0-0 libpangocairo-1.0-0 \
    libgtk-3-0 libgstreamer1.0-0 libgstreamer-plugins-base1.0-0 libxss1 \
    libgconf-2-4 libxtst6 libdrm2 libxcursor1 libxi6 \
    && rm -rf /var/lib/apt/lists/* && apt-get clean && apt-get autoremove -y

# Set timezone
RUN ln -sf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

# Working directory
WORKDIR /app

# Copy requirements first for caching
COPY requirements.txt .

# Install Python deps + Playwright
RUN pip install --no-cache-dir -r requirements.txt && \
    pip install playwright

# Install Playwright browsers with system deps
RUN playwright install --with-deps chromium

# Copy application code
COPY . .

# Prepare directories
RUN mkdir -p logs exports /tmp/chrome-user-data && \
    chown -R appuser:appuser /app /tmp/chrome-user-data && \
    chmod -R 755 /app /tmp/chrome-user-data

# Switch to non-root user
USER appuser

# Expose port
EXPOSE ${PORT:-10000}

# Production env vars
ENV PYTHONPATH=/app \
    HOST=0.0.0.0 \
    PORT=${PORT:-10000} \
    HEADLESS=true \
    PLAYWRIGHT_BROWSERS_PATH=/home/appuser/.cache/ms-playwright

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD python -c "import requests; requests.get(f'http://localhost:${PORT:-10000}/health', timeout=5)" || exit 1

# Start the application (fixed to run the script directly)
CMD ["python", "arbitrage.py"]
