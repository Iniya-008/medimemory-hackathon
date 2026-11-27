FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
# Tesseract OCR with English + major Indian languages (Debian packages)
RUN apt-get update && apt-get install -y --no-install-recommends \
      tesseract-ocr tesseract-ocr-eng tesseract-ocr-tam tesseract-ocr-hin tesseract-ocr-tel tesseract-ocr-kan \
      tesseract-ocr-mal tesseract-ocr-ben tesseract-ocr-mar tesseract-ocr-guj tesseract-ocr-pan \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 8000
# Tables are created on startup (AUTO_INIT_DB). Render provides $PORT.
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
