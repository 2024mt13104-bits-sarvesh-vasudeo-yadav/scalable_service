
# Use a lightweight Python base image
FROM python:3.13-slim

# Set the working directory inside the container
WORKDIR /app

# Copy the dependency file first
COPY requirements.txt .

# Install only the packages needed to run the service
RUN pip install --no-cache-dir fastapi "uvicorn[standard]"

# Copy application source files
COPY app.py common.py ./

# Create a directory for persistent SQLite data
RUN mkdir -p /data

# Configure the application
ENV PORT=8002
ENV DB_PATH=/data/inventory.db
ENV LOG_LEVEL=INFO

# Document the port used by this service
EXPOSE 8002

# Start the FastAPI application
CMD ["sh", "-c", "uvicorn app:app --host 0.0.0.0 --port ${PORT}"]
