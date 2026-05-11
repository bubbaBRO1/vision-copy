FROM python:3.11-slim

WORKDIR /app

# System deps for OpenCV, face_recognition, pytesseract, pyzbar
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    cmake \
    libopencv-dev \
    libboost-python-dev \
    libdlib-dev \
    tesseract-ocr \
    tesseract-ocr-eng \
    libzbar0 \
    libzbar-dev \
    libssl-dev \
    curl \
    chromium \
    chromium-driver \
    && rm -rf /var/lib/apt/lists/*

ENV TESSDATA_PREFIX=/usr/share/tesseract-ocr/5/tessdata

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Playwright browsers
RUN playwright install chromium --with-deps || true

COPY . .

CMD ["sh", "-c", "alembic upgrade head && uvicorn main:app --host 0.0.0.0 --port 8000 --workers 2"]
