# 1. Use the official Microsoft Azure Functions Python image
FROM mcr.microsoft.com/azure-functions/python:4-python3.11

# 2. Set the working directory inside the container
WORKDIR /home/site/wwwroot

# 3. Install system dependencies for Postgres (psycopg2)
RUN apt-get update && apt-get install -y libpq-dev gcc

# 4. Copy and install Python requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 5. Copy the rest of your project code
# This pulls in your /src, /Tables, and your main script
COPY . .

# 6. Set environment variables (Azure usually handles these,
# but this tells the function where the entry point is)
ENV AzureWebJobsScriptRoot=/home/site/wwwroot \
    AzureFunctionsJobHost__Logging__Console__IsEnabled=true