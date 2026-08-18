# Forma — самостоятельное развёртывание на сервере

Этот документ описывает запуск **Forma** на собственном сервере. Итоговая topology состоит из единого FastAPI deployable, который обслуживает React SPA и `/api/v1`, PostgreSQL, Redis, RabbitMQ, outbox publisher и event workers. Внешние порты базы, Redis и RabbitMQ не публикуются: они доступны только внутри Docker network.

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
| `FORMA_WEB_APP_BASE_URL` | Тот же публичный HTTPS URL; используется только для signed verification links в email |
| `POSTGRES_*` | Учётные данные единственного доменного хранилища |
| `RABBITMQ_DEFAULT_*` | Учётные данные брокера событий |
| `REDIS_PASSWORD` | Пароль временного cache/lock хранилища |
| `JWT_SECRET` | Ключ верификации production Bearer JWT; минимум 32 случайных байта |
| `GOOGLE_CALENDAR_CLIENT_ID`, `GOOGLE_CALENDAR_CLIENT_SECRET`, `GOOGLE_CALENDAR_REDIRECT_URI` | Параметры OAuth web client для Google Calendar |
| `INTEGRATION_ENCRYPTION_KEY` | Отдельный 32-byte URL-safe base64 ключ шифрования refresh/access tokens; не используйте для него `JWT_SECRET` |
| `RESEND_API_KEY`, `RESEND_FROM_EMAIL` | Параметры реальной email-доставки через Resend |

## 3. Первый запуск

Production compose-файл находится в `deploy/docker-compose.production.yml`. Он автоматически запускает `migrate`, ждёт успешного применения Alembic migration и только затем поднимает API и worker-процессы.

```bash
docker compose --env-file .env -f deploy/docker-compose.production.yml pull
docker compose --env-file .env -f deploy/docker-compose.production.yml up -d --build
docker compose --env-file .env -f deploy/docker-compose.production.yml ps
```

Проверьте FastAPI API и React SPA локально на сервере:

```bash
curl http://127.0.0.1:8080/health
docker compose --env-file .env -f deploy/docker-compose.production.yml logs --tail=100 api
docker compose --env-file .env -f deploy/docker-compose.production.yml logs --tail=100 worker-outbox worker-events
```

Ожидаемый ответ health endpoint: `ok`. Сервис `api` доступен только по `127.0.0.1:8080`; это преднамеренно, чтобы публичный доступ проходил исключительно через TLS reverse proxy. Собранный React SPA находится в том же production image и отдаётся FastAPI с SPA fallback, а `/api/v1` остаётся versioned REST/BFF boundary.

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

Frontend и API используют один public origin: React обращается только к `/api/v1` через FastAPI/BFF boundary. После подключения issuer добавьте access token в client session и убедитесь, что `JWT_SECRET` или public-key verification соответствует выбранному issuer.

## 6. Google Calendar OAuth

1. Создайте OAuth 2.0 Web Client в Google Cloud Console.
2. Добавьте redirect URI: `https://forma.example.com/api/v1/integrations/calendar/google/callback`.
3. Добавьте `GOOGLE_CALENDAR_CLIENT_ID`, `GOOGLE_CALENDAR_CLIENT_SECRET`, `GOOGLE_CALENDAR_REDIRECT_URI` и независимый `INTEGRATION_ENCRYPTION_KEY` в `.env`.
4. Перезапустите только API и workers:

```bash
docker compose --env-file .env -f deploy/docker-compose.production.yml up -d --force-recreate api worker-outbox worker-events
```

Текущий adapter использует signed OAuth state, encrypted token persistence, callback code exchange и provider-backed **inbound import** Google events в нормализованные `CalendarEvent`/`ExternalEventLink` с cursor и worker outcome. Внешний календарь не является источником доменной истины.

> **Явно отложенный scope:** outbound projection новых внутренних `CalendarEvent` в Google Calendar в этой итерации не реализована. Она требует отдельной conflict policy, стратегии удаления/изменения и двусторонней идемпотентности; не включайте её обходными прямыми вызовами из HTTP router. До отдельного milestone Forma импортирует provider events, но не экспортирует внутренние события во внешний календарь.

Перед передачей production credentials обязательно выполните real-host проверку: OAuth redirect, callback, token encryption и import одной тестовой Google event. Это нельзя подтвердить без ваших credentials и публичного HTTPS domain.

## 7. Email notifications

Для email delivery добавьте `RESEND_API_KEY`, `RESEND_FROM_EMAIL` и `FORMA_WEB_APP_BASE_URL` в `.env`, затем перезапустите API/workers. Без этих настроек in-app notifications и queued records остаются рабочими, но наружная отправка не выполняется. Проверьте, что домен отправителя подтверждён у выбранного провайдера.

При первом создании или смене profile email Forma в той же PostgreSQL transaction записывает `EmailVerificationRequested` в outbox. Event worker отправляет через Resend signed link, действующую 24 часа; raw token не попадает в PostgreSQL, API response или RabbitMQ event payload. Проверьте flow на self-hosted host: создайте workspace, обновите profile email, откройте link из письма и убедитесь, что `GET /api/v1/workspaces/profile` показывает `email_verified: true`.

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
| UI отвечает 502 | `curl 127.0.0.1:8080/health`, `systemctl status caddy` | Убедитесь, что `api` запущен, healthy и Caddy проксирует на 127.0.0.1:8080 |
| OAuth ошибка | API logs + redirect URI | Сверьте домен, HTTPS и callback URL в Google Cloud Console |
| Нет verification email | Logs `worker-outbox worker-events` | Проверьте ключ, подтверждённый sender domain, `FORMA_WEB_APP_BASE_URL`, HTTPS доступность domain и worker receipt `verification-email-worker` |

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
