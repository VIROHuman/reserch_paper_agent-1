FROM python:3.11-slim
WORKDIR /app
RUN apt-get update && apt-get install -y \
    libxml2-dev \
    libxslt1-dev \
    python3-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY server/ ./server/
COPY run_server.py .
RUN mkdir -p uploads
EXPOSE 8000
CMD ["python", "run_server.py"]
