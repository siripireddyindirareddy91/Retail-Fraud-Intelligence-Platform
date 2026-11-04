FROM python:3.12-slim
WORKDIR /app
COPY backend/requirements.lock.txt ./requirements.lock.txt
RUN python -m pip install --no-cache-dir -r requirements.lock.txt
COPY backend/ ./
RUN useradd --create-home --uid 10001 researcher && mkdir -p /data/artifacts && chown -R researcher:researcher /app /data
USER researcher
EXPOSE 8000
CMD ["python", "-m", "uvicorn", "app.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]
