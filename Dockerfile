FROM python:3.12-slim

WORKDIR /app

# تثبيت Docker وأدوات البناء
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    python3-dev \
    docker.io \
 && rm -rf /var/lib/apt/lists/*

# نسخ ملفات المشروع
COPY . .

# تثبيت متطلبات البوت
RUN python -m pip install --upgrade pip setuptools wheel \
 && pip install --no-cache-dir -r "requirements (6).txt"

# تثبيت مكتبة docker-py للتحكم في Docker
RUN pip install docker

# سكريبت البدء (سنضعه في الخطوة التالية)
COPY start.sh /start.sh
RUN chmod +x /start.sh

CMD ["/start.sh"]
