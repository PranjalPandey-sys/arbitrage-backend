# Use the correct Playwright image compatible with v1.40.0
FROM mcr.microsoft.com/playwright/python:v1.40.0-jammy

# Set working directory to project root
WORKDIR /code

# Copy project files
COPY . .

# Make Python output unbuffered (helps with container logs)
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/code

# Upgrade pip and install dependencies
RUN pip install --upgrade pip
RUN pip install -r requirements.txt

# Install Playwright dependencies and browsers
RUN playwright install --with-deps chromium

# Expose FastAPI port
EXPOSE 8000

# Run app with Uvicorn so it binds to all interfaces in container
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--log-level", "info"]
