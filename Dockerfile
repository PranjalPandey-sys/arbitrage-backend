# --- Use official Playwright image with browsers preinstalled ---
FROM mcr.microsoft.com/playwright:v1.47.0-jammy

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    TZ=Asia/Kolkata \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright

# --- Install Python and your app dependencies ---
COPY requirements.txt /app/requirements.txt
RUN apt-get update && apt-get install -y python3 python3-pip && \
    pip install --no-cache-dir -r /app/requirements.txt

# --- Copy project code and fix permissions ---
COPY . /app
RUN chmod -R 777 /app

# --- Run as non-root user ---
USER pwuser

EXPOSE 10000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "10000"]
