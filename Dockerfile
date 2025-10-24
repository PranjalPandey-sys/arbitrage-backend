# Use the latest compatible Playwright base image
FROM mcr.microsoft.com/playwright/python:v1.40.0-jammy

# Set working directory
WORKDIR /app

# Copy project files
COPY . /app

# Install Python dependencies
RUN pip install --upgrade pip
RUN pip install -r requirements.txt

# Expose the port for FastAPI
EXPOSE 8000

# Ensure Playwright browsers are installed
RUN playwright install --with-deps

# Start the FastAPI app
CMD ["python", "app/main.py"]
