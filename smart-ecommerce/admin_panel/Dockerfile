FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1
WORKDIR /app/admin_panel
COPY admin_panel/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY admin_panel/ .
EXPOSE 8001
CMD ["sh", "-c", "python manage.py migrate --noinput && python manage.py collectstatic --noinput && gunicorn config.wsgi:application -b 0.0.0.0:8001 --workers 2"]
