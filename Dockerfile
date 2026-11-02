FROM python:3.12-slim-bookworm

WORKDIR /app

# Menjalankan container dengan non-root user demi keamanan runtime
RUN apt update -y && apt upgrade -y
RUN useradd -m appuser

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
RUN chown -R appuser:appuser /app

USER appuser
EXPOSE 5000

CMD ["gunicorn", "--bind", "0.0.0.0:5000", "app:app"]