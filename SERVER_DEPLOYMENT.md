# Forma — самостоятельное развёртывание на сервере

Этот документ описывает запуск **Forma** на собственном сервере. Итоговая topology состоит из React SPA за Nginx, FastAPI API, PostgreSQL, Redis, RabbitMQ, outbox publisher и event workers. Внешние порты базы, Redis и RabbitMQ не публикуются: они доступны только внутри Docker network.

> **Архитектурное правило:** PostgreSQL является источником доменной истины. Redis хранит только cache/locks, RabbitMQ используется как транспорт `EventBus`, а каждое асинхронное доменное событие сначала записывается в PostgreSQL outbox.

## 1. Требования сервера

Рекомендуемая начальная конфигурация — Ubuntu 24.04 LTS, 2 vCPU, 4 GB RAM, 30 GB SSD, публичный IP и доменное имя. Для личной первой версии можно начать с 2 GB RAM, но RabbitMQ, PostgreSQL и два worker-процесса будут конкурировать за память.

На сервере должны быть установлены Git, Docker Engine и Docker Compose plugin. Выполните команды от пользователя с правом `sudo`:

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y git ca-certificates curl ufw

curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker "$USER"
newgrp docker

docker --version
docker compose version
```

Разрешите только SSH, HTTP и HTTPS. Если используете SSH на другом порту, замените `OpenSSH` соответствующим правилом.

```bash
sudo ufw allow OpenSSH
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw enable
```

## 2. Получение исходного кода и secrets

Клонируйте репозиторий в каталог, доступный вашему deployment-пользователю:

```bash
git clone https://github.com/AveGeorges/FormaYourFutureBeginsToday.git forma
cd forma
cp .env.production.example .env
chmod 600 .env
```

Откройте `.env` и заполните секреты. Ни один placeholder из примера не должен остаться в production. Для каждого пароля и `JWT_SECRET` сгенерируйте независимое значение:

```bash
openssl rand -base64 48
```

Минимальный набор переменных:

| Переменная | Назначение |
|---|---|
| `FORMA_PUBLIC_ORIGIN` | Публичный HTTPS URL, например `https://forma.example.com` |
| `POSTGRES_*` | Учётные данные единственного доменного хранилища |
| `RABBITMQ_DEFAULT_*` | Учётные данные брокера событий |
| `REDIS_PASSWORD` | Пароль временного cache/lock хранилища |
| `JWT_SECRET` | Ключ верификации production Bearer JWT; минимум 32 случайных байта |
| `GOOGLE_CALENDAR_*` | Нужны только для включения Google Calendar OAuth |
| `RESEND_API_KEY`, `EMAIL_FROM` | Нужны только для реальной email-доставки |

## 3. Первый запуск

Production compose-файл находится в `deploy/docker-compose.production.yml`. Он автоматически запускает `migrate`, ждёт успешного применения Alembic migration и только затем поднимает API и worker-процессы.

```bash
docker compose --env-file .env -f deploy/docker-compose.production.yml pull
docker compose --env-file .env -f deploy/docker-compose.production.yml up -d --build
docker compose --env-file .env -f deploy/docker-compose.production.yml ps
```

Проверьте API и frontend локально на сервере:

```bash
curl http://127.0.0.1:8080/health
docker compose --env-file .env -f deploy/docker-compose.production.yml logs --tail=100 api
docker compose --env-file .env -f deploy/docker-compose.production.yml logs --tail=100 worker-outbox worker-events
```

Ожидаемый ответ health endpoint: `ok`. Сервис `frontend` доступен только по `127.0.0.1:8080`; это преднамеренно, чтобы публичный доступ проходил исключительно через TLS reverse proxy.

## 4. Домен и TLS

Создайте DNS A-record `forma.example.com`, указывающую на публичный IPv4 вашего сервера. Дождитесь распространения DNS, затем используйте Caddy как host-level TLS reverse proxy. Установите Caddy:

```bash
sudo apt install -y debian-keyring debian-archive-keyring apt-transport-https
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | sudo gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' | sudo tee /etc/apt/sources.list.d/caddy-stable.list
sudo apt update && sudo apt install -y caddy
```

Скопируйте шаблон конфигурации и замените доменное имя:

```bash
sudo cp deploy/Caddyfile /etc/caddy/Caddyfile
sudo nano /etc/caddy/Caddyfile
sudo caddy validate --config /etc/caddy/Caddyfile
sudo systemctl reload caddy
```

Caddy автоматически выпустит и обновит TLS-сертификат. После этого проверьте:

```bash
curl -I https://forma.example.com/health
curl -I https://forma.example.com/api/v1/health
```

## 5. Первое создание workspace и production authentication

В development режиме React способен создать временный local workspace через `X-User-Id`. В **production** FastAPI принимает только Bearer JWT. До публичного запуска подключите ваш JWT issuer или OAuth provider к production auth adapter; не включайте development header в production.

Фронтенд и API уже разделены: React обращается только к `/api/v1` через Nginx/BFF. После подключения issuer добавьте access token в client session и убедитесь, что `JWT_SECRET` или public-key verification соответствует выбранному issuer.

## 6. Google Calendar OAuth

1. Создайте OAuth 2.0 Web Client в Google Cloud Console.
2. Добавьте redirect URI: `https://forma.example.com/api/v1/integrations/calendar/google/callback`.
3. Добавьте `GOOGLE_CALENDAR_CLIENT_ID` и `GOOGLE_CALENDAR_REDIRECT_URI` в `.env`.
4. Перезапустите только API и workers:

```bash
docker compose --env-file .env -f deploy/docker-compose.production.yml up -d --force-recreate api worker-outbox worker-events
```

Текущий adapter уже использует нормализованное внутреннее событие и `ExternalEventLink`; внешний календарь не является источником доменной истины. Перед передачей production credentials реализуйте server-side encrypted token persistence и callback token exchange как отдельный security review.

## 7. Email notifications

Для email delivery добавьте `RESEND_API_KEY` и `EMAIL_FROM` в `.env`, затем перезапустите API/workers. Без этих настроек in-app notifications и queued records остаются рабочими, но наружная отправка не выполняется. Проверьте, что домен отправителя подтверждён у выбранного провайдера.

## 8. Обновление версии

Перед обновлением обязательно создайте PostgreSQL backup. Затем получите новую версию, пересоберите образы и просмотрите миграции через логи `migrate`:

```bash
./deploy/backup-postgres.sh
git pull --ff-only origin main
docker compose --env-file .env -f deploy/docker-compose.production.yml up -d --build
docker compose --env-file .env -f deploy/docker-compose.production.yml logs --tail=100 migrate
```

## 9. Бэкапы и восстановление

Скрипт `deploy/backup-postgres.sh` создаёт compressed logical dump. Запускайте его по расписанию хоста или через внешний backup service; храните копии вне самого сервера.

```bash
./deploy/backup-postgres.sh
gunzip -c backups/forma-YYYYMMDD-HHMMSS.sql.gz | \
  docker compose --env-file .env -f deploy/docker-compose.production.yml exec -T postgres \
  psql -U "$POSTGRES_USER" -d "$POSTGRES_DB"
```

Перед восстановлением сделайте новый backup и остановите API/workers, чтобы не записывать данные параллельно:

```bash
docker compose --env-file .env -f deploy/docker-compose.production.yml stop api worker-outbox worker-events
```

## 10. Операционная диагностика

| Симптом | Проверка | Действие |
|---|---|---|
| API не стартует | `docker compose ... logs api` | Проверьте `migrate`, `JWT_SECRET`, PostgreSQL URL и healthcheck базы |
| Worker не обрабатывает события | `docker compose ... logs worker-outbox worker-events` | Проверьте RabbitMQ, outbox rows, retry/DLQ и worker receipts |
| UI отвечает 502 | `curl 127.0.0.1:8080/health`, `systemctl status caddy` | Убедитесь, что `frontend` запущен и Caddy проксирует на 127.0.0.1:8080 |
| OAuth ошибка | API logs + redirect URI | Сверьте домен, HTTPS и callback URL в Google Cloud Console |
| Нет email | Logs worker events | Проверьте ключ, подтверждённый sender domain и delivery attempts |

## 11. Полезные команды

```bash
# Все сервисы
docker compose --env-file .env -f deploy/docker-compose.production.yml ps

# Логи в реальном времени
docker compose --env-file .env -f deploy/docker-compose.production.yml logs -f api worker-outbox worker-events

# Ручное применение миграций
docker compose --env-file .env -f deploy/docker-compose.production.yml run --rm migrate

# Остановка без удаления данных
docker compose --env-file .env -f deploy/docker-compose.production.yml down

# Полное удаление включая database volume — использовать только осознанно
docker compose --env-file .env -f deploy/docker-compose.production.yml down -v
```
