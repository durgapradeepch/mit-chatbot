# Use Python 3.13 slim image
FROM python:3.13-slim

# Set working directory
WORKDIR /app

# Install dependencies first (better caching)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY app/ ./app/

# Expose the API port
EXPOSE 8000

# Start the server
CMD ["uvicorn", "app.server:app", "--host", "0.0.0.0", "--port", "8000"]
