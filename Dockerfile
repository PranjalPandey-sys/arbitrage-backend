# Use Playwright official image
FROM mcr.microsoft.com/playwright/python:latest

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    TZ=Asia/Kolkata \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright

# Install dependencies
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# Copy code
COPY . /app

# Give write permission for logs and other runtime files
RUN chmod -R 777 /app

# Run as non-root user
USER pwuser

EXPOSE 10000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "10000"]
