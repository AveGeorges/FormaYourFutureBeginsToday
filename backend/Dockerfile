FROM python:3.12-slim

WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1

COPY pyproject.toml ./
RUN pip install .

COPY . .
RUN useradd --create-home --shell /usr/sbin/nologin forma && chown -R forma:forma /app
USER forma

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
