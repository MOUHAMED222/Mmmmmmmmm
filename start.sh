#!/bin/bash
set -e

# بدء Docker daemon في الخلفية
dockerd --host=unix:///var/run/docker.sock &
DOCKER_PID=$!
echo "Docker daemon started with PID $DOCKER_PID"

# انتظار حتى يصبح جاهزًا
sleep 10

# تشغيل البوت (إذا كان اسم الملف الرئيسي main.py، وإلا غيّره)
exec python -u main.py
