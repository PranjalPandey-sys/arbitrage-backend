# Use Playwright base image
FROM mcr.microsoft.com/playwright/python:latest

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    TZ=Asia/Kolkata \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright

# Install Python dependencies
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

#  Explicitly install browsers (ensure they exist in /ms-playwright)
RUN python -m playwright install --with-deps chromium

# Copy your code
COPY . /app

# Fix permissions for logging etc.
RUN chmod -R 777 /app

USER pwuser

EXPOSE 10000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "10000"]
