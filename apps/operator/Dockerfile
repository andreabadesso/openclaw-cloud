FROM python:3.12-slim

WORKDIR /app

# Install operator service
COPY pyproject.toml .
RUN pip install --no-cache-dir .

COPY openclaw_operator/ openclaw_operator/

EXPOSE 8081

CMD ["python", "-m", "openclaw_operator.main"]
