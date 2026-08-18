# Forma — настройка профиля, подтверждённого email и уведомлений

Этот документ описывает выбранную для Forma модель: **адрес получателя хранится в self-hosted профиле пользователя**, а не зависит от внешнего JWT issuer. Благодаря этому система уведомлений имеет собственный источник правды для адреса и пользовательского согласия на email-рассылку.

> В текущем checkpoint готовы схема PostgreSQL, REST contract профиля, настройки окружения для Resend, отправка **product notifications** после commit in-app уведомления и transaction-safe отправка **verification email** через Transactional Outbox. Доставка product notifications строго блокируется, пока адрес не подтверждён или пользователь не отключил email-уведомления. Verification link подписан, действует 24 часа и не требует хранения raw token в PostgreSQL.

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

После настройки профиля запросите отправку verification email:

```bash
curl --fail-with-body -X POST "$FORMA_URL/api/v1/workspaces/profile/email-verification" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H "Idempotency-Key: $(uuidgen)"
```

API вернёт `verification_queued`. В этой же транзакции в Transactional Outbox записывается факт `EmailVerificationRequested`; после publish event worker запрашивает актуальный профиль, создаёт короткоживущую signed link и отправляет письмо через Resend. Raw token не возвращается API, не записывается в PostgreSQL и не входит в event payload.

Откройте ссылку из письма в течение 24 часов. Она вызывает публичный endpoint подтверждения и возвращает JSON профиля с `email_verified: true`. Для ручной диагностики можно открыть link целиком из письма; Bearer JWT и `Idempotency-Key` для signed link не требуются, потому что подпись связывает link с конкретными `user_id` и email.

## 5. Переменные окружения для Resend

В `.env` на сервере подготовьте следующие параметры. Не добавляйте реальные значения в Git, `.env.production.example` или клиентский bundle.

```dotenv
RESEND_API_KEY=re_...
RESEND_FROM_EMAIL=Forma <notifications@your-verified-domain.example>
# Должен совпадать с публичным HTTPS origin, доступным из почтового клиента.
FORMA_WEB_APP_BASE_URL=https://forma.example.com
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
| Не хранить raw verification token | Утечка базы не должна позволять подтвердить email. Signed link создаётся worker после outbox commit и действует 24 часа. |
| Не использовать JWT claim как единственный email source | Внешний issuer может поменять claim или прекратить его выдачу. |
| Хранить каждую provider attempt отдельно | Можно диагностировать ошибки и не смешивать in-app с email delivery. |
| Запускать product email только после commit in-app уведомления | Ошибка Resend не меняет receipt idempotency и не переводит RabbitMQ event в DLQ. |

## 7. Product notifications: что отправляется сейчас

После успешного commit in-app уведомления `notification_worker` запускает detached delivery. Он создаёт `EmailDeliveryAttempt` только для delivery attempts, прошедших profile gate. В таблице сохраняются provider result: `delivered` с ID Resend либо `failed` с причиной ошибки. Состояния `skipped_missing_profile`, `skipped_unverified` и `skipped_opt_out` являются нормальным запретом на внешнюю отправку и не меняют статус in-app уведомления.

Пользователю отправляется русскоязычный шаблон для AI proposal/approval, создания или обновления задач и календарных блоков. Для прочих доменных событий применяется нейтральное сообщение без сериализации payload. В содержимое не попадают raw JSON события, токены или секреты.

## 8. Текущая готовность и следующие действия

Готовы профиль, verified-email schema, notification preferences, Resend HTTP adapter, `EmailDeliveryAttempt`, active notification delivery wiring, verification email через Transactional Outbox и signed link, а также mocked coverage profile-gated delivery states, signed link success/expiry и worker receipt idempotency.

Перед production-включением обязательно проверьте flow на собственном домене и реальном Resend sandbox: worker должен быть запущен, `FORMA_WEB_APP_BASE_URL` должен быть доступен по HTTPS, а адрес из `RESEND_FROM_EMAIL` — подтверждён в Resend. Не отмечайте профиль verified вручную и не обходите delivery gate.
