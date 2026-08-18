FROM node:22-alpine AS builder

WORKDIR /app
COPY package.json pnpm-lock.yaml ./
COPY patches ./patches
RUN corepack enable && pnpm install --frozen-lockfile
COPY client ./client
COPY shared ./shared
COPY vite.config.ts tsconfig.json ./
RUN pnpm exec vite build

FROM nginx:1.27-alpine
COPY deploy/nginx/default.conf /etc/nginx/conf.d/default.conf
COPY --from=builder /app/dist/public /usr/share/nginx/html
EXPOSE 80
