# Use the official Python image as the base image
FROM python:3.10-slim-buster

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1
ENV SHOPCANAL_API_BASE_URL "https://api-develop.shopcanal.com/platform"
ENV DB_PATH "/etc/test-api-store-db/db.sqlite3"
ENV CANAL_API_ID "032ab4ad-6195-4017-96fa-fce01baa36c8"
ENV CANAL_ACCESS_TOKEN = "acaae855f7cb4546bcf5defc23968c5e"

# Set the working directory
WORKDIR /app

# Copy the requirements file into the container
COPY requirements.txt .

# Install the required packages
RUN pip install --upgrade pip
RUN pip install -r requirements.txt

# Copy the rest of the application code into the container
COPY . .

# Expose the port the app will run on
EXPOSE 80

# Start the Django development server
CMD ["python", "manage.py", "runserver", "0.0.0.0:80"]