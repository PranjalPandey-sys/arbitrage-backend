# Use Playwright's official Python image that includes browsers and dependencies.
# Use an image tag close to your playwright version; adjust the tag if desired.
FROM mcr.microsoft.com/playwright/python:1.40.0

# Working dir
WORKDIR /app

# Environment
ENV PYTHONUNBUFFERED=1 \
    TZ=Asia/Kolkata \
    # expose Playwright browsers path (not required but explicit)
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright

# Copy requirements and install Python deps (pip is available in the base image)
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# Copy app code
COPY . /app

# The base image runs as non-root user 'pwuser' (non-root). Leave as-is so the container runs non-root.
# If you need a different username, you can add one, but it's not necessary.
USER pwuser

# Optional: expose same port you use (Procfile or Render env may override)
EXPOSE 10000

# Healthcheck (optional)
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
  CMD curl --fail http://localhost:${PORT:-10000}/health || exit 1

# Default command (adjust if you use Procfile on Render)
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "10000", "--workers", "1"]
