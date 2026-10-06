FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1
WORKDIR /app/api
COPY api/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY api/ .
COPY frontend/ /app/frontend/
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
