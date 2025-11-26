FROM python:3.11-slim

# Set the working directory in the container
WORKDIR /app

# Copy only requirements first to leverage Docker cache
COPY requirements.txt .

# Upgrade pip and install dependencies with retries and longer timeout
RUN pip install --upgrade pip \
    && pip install --no-cache-dir --default-timeout=100 --retries=10 -r requirements.txt

# Copy the rest of the project files
COPY . .

# Expose the port your app runs on
EXPOSE 3002

# Start the Flask app
CMD ["python", "trends_keyword.py"]
