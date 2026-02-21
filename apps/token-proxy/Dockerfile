FROM python:3.12-slim

WORKDIR /app

# Install token-proxy service
COPY apps/token-proxy/pyproject.toml .
RUN pip install --no-cache-dir .

COPY apps/token-proxy/token_proxy/ token_proxy/

ENV PORT=8080
EXPOSE 8080

CMD ["sh", "-c", "uvicorn token_proxy.main:app --host 0.0.0.0 --port ${PORT}"]
