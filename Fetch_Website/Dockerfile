# Use a lightweight official Python image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Copy only requirements first to leverage Docker cache
COPY requirements.txt .

# Upgrade pip and install dependencies with retries, longer timeout, no cache
RUN pip install --upgrade pip \
    && pip install --no-cache-dir --default-timeout=100 --retries=10 -r requirements.txt

# Copy the rest of the project files
COPY . .

# Expose the port your app uses
EXPOSE 3001

# Start the Flask app
CMD ["python", "fetch.py"]
