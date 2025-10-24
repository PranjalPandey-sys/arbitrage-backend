FROM python:3.11-slim

WORKDIR /app

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    TZ=Asia/Kolkata \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright

# Install system dependencies required for Chromium
RUN apt-get update && apt-get install -y --no-install-recommends \
    wget curl gnupg ca-certificates fonts-liberation libasound2 libatk-bridge2.0-0 libatk1.0-0 \
    libc6 libcups2 libdbus-1-3 libdrm2 libgbm1 libgtk-3-0 libnspr4 libnss3 libx11-6 \
    libxcomposite1 libxdamage1 libxrandr2 libxss1 libxshmfence1 libpangocairo-1.0-0 \
    libpango-1.0-0 lsb-release xdg-utils && \
    rm -rf /var/lib/apt/lists/*

# Install Python dependencies and Playwright
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt && \
    pip install --no-cache-dir playwright

# Install Chromium browsers inside the image
RUN python -m playwright install --with-deps chromium

# Copy project files
COPY . /app

# Give write permission to app files
RUN chmod -R 777 /app

# Create and use non-root user
RUN useradd -m appuser
USER appuser

EXPOSE 10000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "10000"]
