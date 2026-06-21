FROM python:3.12-slim

# Prevent Python from writing .pyc files to disk
ENV PYTHONDONTWRITEBYTECODE=1
# Prevent Python from buffering stdout/stderr
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Copy requirements and install dependencies
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code
COPY . /app/

# Ensure the mock database file exists so Docker bind-mounts don't create it as a directory
RUN touch bookings.json

# Default to running the interactive CLI
CMD ["python", "main.py"]
