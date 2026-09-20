FROM python:3.12-slim
WORKDIR /code
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 8000
# Shell form so $PORT (Render, Railway, Fly, ...) is honoured; defaults to 8000 locally.
CMD uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}
