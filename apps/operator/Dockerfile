FROM python:3.12-slim

WORKDIR /app

# Install shared package first
COPY apps/shared/ /tmp/shared/
RUN pip install --no-cache-dir /tmp/shared/ && rm -rf /tmp/shared/

# Install operator service
COPY apps/operator/pyproject.toml .
RUN pip install --no-cache-dir .

COPY apps/operator/openclaw_operator/ openclaw_operator/

EXPOSE 8081

CMD ["python", "-m", "openclaw_operator.main"]
