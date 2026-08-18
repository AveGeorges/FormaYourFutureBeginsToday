# Forma — настройка профиля, подтверждённого email и уведомлений

Этот документ описывает выбранную для Forma модель: **адрес получателя хранится в self-hosted профиле пользователя**, а не зависит от внешнего JWT issuer. Благодаря этому система уведомлений имеет собственный источник правды для адреса и пользовательского согласия на email-рассылку.

> В текущем checkpoint готовы схема PostgreSQL, REST contract профиля, одноразовые verification tokens, настройки окружения для Resend и отправка **product notifications** после commit in-app уведомления. Доставка строго блокируется, пока адрес не подтверждён или пользователь не отключил email-уведомления. Отправка **verification email** пока намеренно не включена: для неё требуется отдельный transaction-safe flow, который не хранит raw token и не отправляет ссылку до успешной фиксации token hash в PostgreSQL.

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

В текущей версии API вернёт `verification_queued` и создаст одноразовый token hash со сроком действия 24 часа. Raw token намеренно не возвращается API и не хранится в PostgreSQL.

> **Ограничение текущей версии.** Verification email ещё не отправляется через Resend, поэтому production-подтверждение адреса нельзя завершить только этим API. Не отмечайте профиль как verified вручную и не обходите delivery gate. Следующей отдельной работой будет безопасный verification mail flow через transactional outbox либо одноразовый signed confirmation link.

Когда transaction-safe verification mail flow будет подключён, письмо будет содержать verification link/token. Подтверждение выполняется запросом:

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
| Запускать product email только после commit in-app уведомления | Ошибка Resend не меняет receipt idempotency и не переводит RabbitMQ event в DLQ. |

## 7. Product notifications: что отправляется сейчас

После успешного commit in-app уведомления `notification_worker` запускает detached delivery. Он создаёт `EmailDeliveryAttempt` только для delivery attempts, прошедших profile gate. В таблице сохраняются provider result: `delivered` с ID Resend либо `failed` с причиной ошибки. Состояния `skipped_missing_profile`, `skipped_unverified` и `skipped_opt_out` являются нормальным запретом на внешнюю отправку и не меняют статус in-app уведомления.

Пользователю отправляется русскоязычный шаблон для AI proposal/approval, создания или обновления задач и календарных блоков. Для прочих доменных событий применяется нейтральное сообщение без сериализации payload. В содержимое не попадают raw JSON события, токены или секреты.

## 8. Текущая готовность и следующие действия

Готовы профиль, verified-email schema, notification preferences, Resend HTTP adapter, `EmailDeliveryAttempt`, active notification delivery wiring и mocked integration coverage для `delivered`, `failed`, `skipped_missing_profile`, `skipped_unverified` и `skipped_opt_out`.

До полностью end-to-end verified-email flow остаётся один самостоятельный этап: отправка verification message через transaction-safe provider/outbox flow без хранения raw token в PostgreSQL. Он остаётся открытым в `todo.md` и `CHANGELOG_AI.md`. До его завершения deployment можно использовать для in-app уведомлений и для внешней доставки только уже подтверждённым профилям, созданным через будущий безопасный verification flow.
