FROM python:3.12-slim
# slim base - habit 1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
# deps BEFORE code - habit 4 (the cache trick)

COPY app.py .
# code last

RUN useradd -m appuser
USER appuser
# never root - habit 5

EXPOSE 8000

HEALTHCHECK CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1
# the app tells Docker it's actually alive - habit 7

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
# array form CMD - and note: 0.0.0.0, not 127.0.0.1!