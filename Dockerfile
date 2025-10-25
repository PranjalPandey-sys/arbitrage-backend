# Use the correct Playwright image compatible with v1.40.0
FROM mcr.microsoft.com/playwright/python:v1.40.0-jammy

# Set working directory to project root
WORKDIR /code

# Copy project files
COPY . .

# Upgrade pip and install dependencies
RUN pip install --upgrade pip
RUN pip install -r requirements.txt

# Install Playwright dependencies and browsers
RUN playwright install --with-deps chromium

# Expose FastAPI port
EXPOSE 8000

# Set PYTHONPATH to include /code
ENV PYTHONPATH=/code

# Run app
CMD ["python", "app/main.py"]
