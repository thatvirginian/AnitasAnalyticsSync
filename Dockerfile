# 1. Use a lightweight Python image
FROM python:3.11-slim

# 2. Set the working directory
WORKDIR /app

# 3. Install system dependencies for Postgres (needed for psycopg2-binary sometimes)
RUN apt-get update && apt-get install -y libpq-dev gcc && rm -rf /var/lib/apt/lists/*

# 4. Copy requirements and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 5. Copy your project code
# This copies everything (Tables folder, Future_DB_Update.py, etc.)
COPY . .

# 6. Command to run your script
# This is the "Entry Point" for the Job
CMD ["python", "Future_DB_Update.py"]
