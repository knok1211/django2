#!/bin/bash

# 마이그레이션 실행
echo "Running migrations..."
python manage.py migrate --noinput

# Static 파일 수집
echo "Collecting static files..."
python manage.py collectstatic --noinput

# 서버 시작
echo "Starting Django server..."
python manage.py runserver 0.0.0.0:8000