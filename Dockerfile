# Use Python 3.11 slim image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY main.py .

# Set environment variables
ENV PORT=8080
ENV PYTHONUNBUFFERED=1

# Create a non-root user
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

# Run the application with gunicorn
CMD exec gunicorn --bind :$PORT --workers 1 --threads 8 --timeout 0 main:app

