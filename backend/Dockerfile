# Use the official Python image
FROM python:3.9-slim

ENV TRANSFORMERS_CACHE=/app/model_cache
# Set the working directory
WORKDIR /app

# Copy all files
COPY . /app

# Copy the requirements file
COPY requirements.txt .

# Install dependencies
#RUN pip install --no-cache-dir -r requirements.txt
RUN pip install --upgrade pip
RUN pip install --default-timeout=300 -r requirements.txt

# RUN pip install -r requirements.txt

# Copy the application code
COPY . .
COPY linkedin_agent.py .

# Copy Google credentials file (if it exists in backend folder)
# This file will be included in the Docker image
COPY linkedin-agent-478216-f37f2b2ce601.json /app/linkedin-agent-478216-f37f2b2ce601.json

#RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')"
# Expose the port
EXPOSE 5000

# Command to run the application
CMD ["flask", "run", "--host", "0.0.0.0", "--port", "5000"]