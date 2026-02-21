FROM python:3.12-slim

WORKDIR /app

# Install API service
COPY apps/api/pyproject.toml .
RUN pip install --no-cache-dir .

COPY apps/api/openclaw_api/ openclaw_api/

EXPOSE 8000

CMD ["uvicorn", "openclaw_api.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
