# Use official lightweight Python 3.11 image
FROM python:3.11-slim

# Set runtime environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8080 \
    C_FORCE_ROOT=true

# Set working directory
WORKDIR /app

# Install build dependencies if needed
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy and install python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# Copy all project directories and files
COPY . .

# Expose port (Cloud Run defaults to PORT environment variable, which we default to 8080)
EXPOSE 8080

# Default command runs the behavior spec assertions to confirm build health,
# but can be overridden on Cloud Run to launch 'adk web trading_risk_coach'
CMD ["python", "test_sdd_specs.py"]
