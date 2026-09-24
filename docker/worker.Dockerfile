FROM python:3.12-slim

WORKDIR /app
COPY pyproject.toml README.md ./
COPY information_hunters ./information_hunters
RUN pip install --no-cache-dir .
ENV HOST_ID=""
CMD ["python", "-m", "information_hunters.worker"]
