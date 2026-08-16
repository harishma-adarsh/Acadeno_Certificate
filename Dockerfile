# Use an official Python runtime as a parent image
FROM python:3.12-slim


# Install system dependencies for WeasyPrint
RUN apt-get update && apt-get install -y \
    python3-pip \
    python3-cffi \
    python3-brotli \
    libpango-1.0-0 \
    libpangoft2-1.0-0 \
    libharfbuzz0b \
    libharfbuzz-subset0 \
    libjpeg-dev \
    libopenjp2-7-dev \
    libffi-dev \
    libgdk-pixbuf-2.0-0 \
    libglib2.0-0 \
    libcairo2 \
    libpangocairo-1.0-0 \
    shared-mime-info \
    fonts-liberation \
    && rm -rf /var/lib/apt/lists/*





# Set the working directory in the container
WORKDIR /app

# Copy the current directory contents into the container at /app
COPY . /app

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Create directories for DB and PDFs if they don't exist
RUN mkdir -p generated/pdfs

# Make port 10000 available to the world outside this container
EXPOSE 10000

# Define environment variable for Flask
ENV PORT 10000

# Run gunicorn when the container launches
CMD ["gunicorn", "--bind", "0.0.0.0:10000", "--timeout", "900", "--workers", "1", "--threads", "4", "app:app"]
