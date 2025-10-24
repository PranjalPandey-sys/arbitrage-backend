# Use Playwright 1.40.0 base image
FROM mcr.microsoft.com/playwright/python:v1.40.0-jammy

# Set workdir to project root
WORKDIR /code

# Copy everything
COPY . .

# Install dependencies
RUN pip install --upgrade pip
RUN pip install -r requirements.txt

# Ensure browsers are installed
RUN playwright install --with-deps

# Expose FastAPI port
EXPOSE 8000

# Start FastAPI from inside the app folder
CMD ["python", "app/main.py"]
