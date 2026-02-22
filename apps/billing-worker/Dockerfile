FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml .
RUN pip install --no-cache-dir .

COPY billing_worker/ billing_worker/

EXPOSE 8082

CMD ["python", "-m", "billing_worker.main"]
