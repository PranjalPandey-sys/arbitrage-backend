# Use Playwright official image (includes browsers + deps)
FROM mcr.microsoft.com/playwright/python:latest

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    TZ=Asia/Kolkata \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright

# Install python deps
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# Copy code
COPY . /app

# Run as provided non-root user (pwuser exists in this base image)
USER pwuser

EXPOSE 10000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "10000"]
