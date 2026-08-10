FROM python:3.12-slim AS builder

# تثبيت الأدوات الأساسية
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    gnupg \
    ca-certificates \
    build-essential \
    python3-dev \
    git \
    && rm -rf /var/lib/apt/lists/*

# تثبيت Node.js 20.x LTS (بدلاً من 18)
RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && rm -rf /var/lib/apt/lists/*

# تثبيت PHP 8.2 و Composer
RUN apt-get update && apt-get install -y --no-install-recommends \
    php8.2 \
    php8.2-cli \
    php8.2-mbstring \
    php8.2-xml \
    php8.2-curl \
    php8.2-zip \
    php8.2-bcmath \
    php8.2-json \
    && php -r "copy('https://getcomposer.org/installer', 'composer-setup.php');" \
    && php composer-setup.php --install-dir=/usr/local/bin --filename=composer \
    && php -r "unlink('composer-setup.php');" \
    && rm -rf /var/lib/apt/lists/*

# تعيين متغيرات البيئة لتثبيت حزم Python محليًا
ENV PYTHONUSERBASE=/app/.local \
    PATH=/app/.local/bin:$PATH

# نسخ ملف المتطلبات وتثبيتها
COPY requirements*.txt ./
RUN pip install --upgrade pip setuptools wheel \
    && pip install --user --no-cache-dir -r requirements*.txt \
    && pip install --user docker

# نسخ باقي المشروع
COPY . .

# صورة نهائية
FROM python:3.12-slim

# نسخ التثبيتات من المرحلة السابقة
COPY --from=builder /usr/local/bin /usr/local/bin
COPY --from=builder /usr /usr
COPY --from=builder /app /app
COPY --from=builder /root/.local /root/.local

ENV PYTHONUSERBASE=/app/.local \
    PATH=/app/.local/bin:/usr/local/bin:/usr/bin:/bin

WORKDIR /app

CMD ["python", "main.py"]
