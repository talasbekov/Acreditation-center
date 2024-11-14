FROM python:3.10-slim-buster

# Install dependencies
RUN pip install --upgrade pip
RUN pip install pipenv

# Set working directory
WORKDIR /app

# Install wget
RUN apt-get update && apt-get install libssl-dev wkhtmltopdf -y

# Copy Pipfile and Pipfile.lock
COPY requirements.txt .

# Install dependencies
RUN pip install -r requirements.txt
#COPY ./api/v1/docs/cities.csv /app/docs/cities.csv

# Copy project
COPY . .