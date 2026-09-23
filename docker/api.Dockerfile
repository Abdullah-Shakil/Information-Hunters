FROM python:3.12-slim

WORKDIR /app
COPY pyproject.toml README.md ./
COPY information_hunters ./information_hunters
RUN pip install --no-cache-dir .
EXPOSE 8000
CMD ["uvicorn", "information_hunters.api:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
