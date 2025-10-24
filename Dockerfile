# Use the latest Playwright base image that matches the Python package
FROM mcr.microsoft.com/playwright/python:v1.40.0-jammy

# Set working directory
WORKDIR /app

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install --upgrade pip
RUN pip install -r requirements.txt

# Copy all project files
COPY . .

# Expose the port Render expects
ENV PORT=10000
EXPOSE 10000

# Start the app
CMD ["python", "app/main.py"]
