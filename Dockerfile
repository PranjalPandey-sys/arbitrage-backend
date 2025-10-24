# Final recommended Dockerfile for Render (robust + Playwright browsers present)
# Uses Playwright's maintained Python image which includes the native browser runtimes.
FROM mcr.microsoft.com/playwright/python:latest

# Working dir where the repo will be copied
WORKDIR /app

# Ensure the base image uses the same browswer cache path
ENV PLAYWRIGHT_BROWSERS_PATH=/ms-playwright \
    PYTHONUNBUFFERED=1 \
    TZ=Asia/Kolkata \
    PORT=10000

# Install application dependencies (cache with Docker layers)
COPY requirements.txt /app/requirements.txt
RUN pip install --upgrade pip
RUN pip install --no-cache-dir -r /app/requirements.txt

# Copy project files
COPY . /app

# Ensure runtime user can write logs and temp files
RUN chmod -R 777 /app

# Run as the non-root pwuser included in the Playwright image
USER pwuser

# Use the module entrypoint so Python resolves the 'app' package consistently
EXPOSE 10000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "10000"]
