# Use the official Python image
FROM python:3.9-slim

ENV TRANSFORMERS_CACHE=/app/model_cache
# Set the working directory
WORKDIR /app

# Copy the requirements file
COPY requirements.txt .

# Install dependencies
#RUN pip install --no-cache-dir -r requirements.txt
RUN pip install -r requirements.txt

# Copy the application code
COPY app.py .

#RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')"
# Expose the port
EXPOSE 5000

# Command to run the application
CMD ["flask", "run", "--host", "0.0.0.0", "--port", "5000"]