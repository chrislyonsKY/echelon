FROM python:3.12-slim

# Install system dependencies for PostGIS / GDAL / rasterio
RUN apt-get update && apt-get install -y --no-install-recommends \
    gdal-bin \
    libgdal-dev \
    libpq-dev \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Non-root user
RUN useradd -m -u 1000 echelon
WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir setuptools wheel && \
    pip install --no-cache-dir -r requirements.txt

COPY . .
RUN chown -R echelon:echelon /app
USER echelon

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
