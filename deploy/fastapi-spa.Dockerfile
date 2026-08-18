FROM node:22-alpine AS frontend-builder

WORKDIR /build
COPY package.json pnpm-lock.yaml ./
COPY patches ./patches
RUN corepack enable && pnpm install --frozen-lockfile
COPY client ./client
COPY shared ./shared
COPY vite.config.ts tsconfig.json ./
RUN pnpm exec vite build

FROM python:3.12-slim

WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
COPY backend ./
RUN pip install .
COPY --from=frontend-builder /build/dist/public /app/web
RUN useradd --create-home --shell /usr/sbin/nologin forma && chown -R forma:forma /app
USER forma

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
