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

# تثبيت Node.js 20.x LTS
RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && rm -rf /var/lib/apt/lists/*

# تثبيت PHP (الإصدار الافتراضي) والملحقات المطلوبة
RUN apt-get update && apt-get install -y --no-install-recommends \
    php \
    php-mbstring \
    php-xml \
    php-curl \
    php-zip \
    php-bcmath \
    && php -r "copy('https://getcomposer.org/installer', 'composer-setup.php');" \
    && php composer-setup.php --install-dir=/usr/local/bin --filename=composer \
    && php -r "unlink('composer-setup.php');" \
    && rm -rf /var/lib/apt/lists/*

# تعيين مسار تثبيت حزم Python محليًا
ENV PYTHONUSERBASE=/app/.local \
    PATH=/app/.local/bin:$PATH

# نسخ ملف المتطلبات وتثبيتها
COPY requirements*.txt ./
RUN pip install --upgrade pip setuptools wheel \
    && pip install --user --no-cache-dir -r requirements*.txt \
    && pip install --user docker

# نسخ باقي المشروع
COPY . .

# صورة نهائية أصغر
FROM python:3.12-slim

# نسخ التثبيتات من المرحلة السابقة
COPY --from=builder /usr/local/bin /usr/local/bin
COPY --from=builder /usr /usr
COPY --from=builder /app /app
# نسخ حزم Python المثبتة محليًا (تم وضعها في /app/.local)
COPY --from=builder /app/.local /app/.local

ENV PYTHONUSERBASE=/app/.local \
    PATH=/app/.local/bin:/usr/local/bin:/usr/bin:/bin

WORKDIR /app

CMD ["python", "main.py"]
