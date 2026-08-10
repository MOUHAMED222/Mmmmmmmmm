FROM python:3.12-slim

# تثبيت الأدوات الأساسية و Node.js و PHP
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

# تثبيت PHP والملحقات المطلوبة
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

# تعيين دليل العمل
WORKDIR /app

# نسخ ملف المتطلبات (تأكد من تسميته requirements.txt)
COPY requirements.txt ./
RUN pip install --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt \
    && pip install docker

# نسخ باقي المشروع
COPY . .

# التحقق من وجود الملفات (للتأكد أثناء البناء)
RUN ls -la /app

# تشغيل البوت مع تفريغ المخرجات فوراً
CMD ["python", "-u", "main.py"]
