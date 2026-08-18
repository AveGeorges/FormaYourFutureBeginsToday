# Forma — настройка профиля, подтверждённого email и уведомлений

Этот документ описывает выбранную для Forma модель: **адрес получателя хранится в self-hosted профиле пользователя**, а не зависит от внешнего JWT issuer. Благодаря этому система уведомлений имеет собственный источник правды для адреса и пользовательского согласия на email-рассылку.

> В текущем checkpoint готовы схема PostgreSQL, REST contract профиля, одноразовые verification tokens и настройки окружения для Resend. Фактическая отправка verification message и product notifications через Resend ещё подключается следующим шагом; не включайте внешнюю отправку до его завершения.

## 1. Что появилось в базе данных

После запуска Alembic migrations Forma создаёт две дополнительные таблицы.

| Таблица | Назначение |
|---|---|
| `user_profiles` | Хранит email, время подтверждения адреса и согласие на email-уведомления для конкретного `user_id`. |
| `email_verification_tokens` | Хранит только SHA-256 hash одноразового verification token, его срок действия и время использования. Сам token в базе не сохраняется. |

Адрес считается пригодным для внешней доставки только при одновременном выполнении двух условий: `email_verified_at` заполнен и `email_notifications_enabled = true`.

## 2. Обновление self-hosted сервера

Перед обновлением создайте backup PostgreSQL и получите свежую версию приложения.

```bash
cd ~/forma
./deploy/backup-postgres.sh
git pull --ff-only origin main
docker compose --env-file .env -f deploy/docker-compose.production.yml up -d --build
docker compose --env-file .env -f deploy/docker-compose.production.yml logs --tail=100 migrate
```

Проверьте, что migrate service завершился успешно и применил revisions `20260818_0004` и `20260818_0005`:

```bash
docker compose --env-file .env -f deploy/docker-compose.production.yml exec -T postgres \
  psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" \
  -c "select version_num from alembic_version;"
```

Ожидаемое значение: `20260818_0005` или более позднее.

## 3. Настройка профиля через API

В production API принимает Bearer JWT. Замените значения ниже на ваш домен и access token. Для любой изменяющей операции формируйте новый UUID для `Idempotency-Key`.

```bash
export FORMA_URL="https://forma.example.com"
export ACCESS_TOKEN="REPLACE_WITH_PRODUCTION_BEARER_JWT"
export IDEMPOTENCY_KEY="$(uuidgen)"
```

Создайте или обновите профиль. При смене email его verified status автоматически сбрасывается до нового подтверждения.

```bash
curl --fail-with-body -X PUT "$FORMA_URL/api/v1/workspaces/profile" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H "Idempotency-Key: $IDEMPOTENCY_KEY" \
  -H "Content-Type: application/json" \
  --data '{
    "email": "you@example.com",
    "email_notifications_enabled": true
  }'
```

Проверьте профиль:

```bash
curl --fail-with-body "$FORMA_URL/api/v1/workspaces/profile" \
  -H "Authorization: Bearer $ACCESS_TOKEN"
```

Ожидаемый ответ до подтверждения имеет вид:

```json
{
  "email": "you@example.com",
  "email_verified": false,
  "email_notifications_enabled": true
}
```

## 4. Запрос подтверждения email

После настройки профиля запросите verification token:

```bash
curl --fail-with-body -X POST "$FORMA_URL/api/v1/workspaces/profile/email-verification" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H "Idempotency-Key: $(uuidgen)"
```

В текущей версии API вернёт `verification_queued`, создаст одноразовый token hash со сроком действия 24 часа и подготовит основу для следующего шага — внешней отправки сообщения. Raw token намеренно не возвращается API и не хранится в PostgreSQL.

Когда Resend adapter будет подключён, письмо будет содержать verification link/token. Подтверждение выполняется запросом:

```bash
curl --fail-with-body -X POST "$FORMA_URL/api/v1/workspaces/profile/email-verification/confirm" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H "Idempotency-Key: $(uuidgen)" \
  -H "Content-Type: application/json" \
  --data '{"token":"TOKEN_FROM_VERIFICATION_MESSAGE"}'
```

После этого `email_verified` станет `true`. Использованный token нельзя применить повторно.

## 5. Переменные окружения для Resend

В `.env` на сервере подготовьте следующие параметры. Не добавляйте реальные значения в Git, `.env.production.example` или клиентский bundle.

```dotenv
RESEND_API_KEY=re_...
RESEND_FROM_EMAIL=Forma <notifications@your-verified-domain.example>
```

У Resend должен быть подтверждён домен отправителя. После изменения `.env` перезапустите API и event worker:

```bash
docker compose --env-file .env -f deploy/docker-compose.production.yml \
  up -d --force-recreate api worker-events
```

## 6. Правила безопасной доставки

| Правило | Причина |
|---|---|
| Не отправлять на непроверенный адрес | Предотвращает доставку на ошибочный или чужой email. |
| Не отправлять при выключенном preference | Пользователь сохраняет контроль над уведомлениями. |
| Не хранить raw verification token | Утечка базы не должна позволять подтвердить email. |
| Не использовать JWT claim как единственный email source | Внешний issuer может поменять claim или прекратить его выдачу. |
| Хранить каждую provider attempt отдельно | Можно диагностировать ошибки и не смешивать in-app с email delivery. |

## 7. Текущая готовность и следующие действия

Профиль, verified-email schema, токены подтверждения и API готовы. До production email delivery ещё необходимо: реализовать Resend HTTP adapter; отправлять verification message с raw token; создавать `EmailDeliveryAttempt` для всех внешних отправок; и добавить integration tests для success/error/opt-out/unverified scenarios. Эти шаги уже зафиксированы в `todo.md` и `CHANGELOG_AI.md`.
