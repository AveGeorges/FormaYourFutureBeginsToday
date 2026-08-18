# Forma — технический статус первой итерации

**Дата:** 18 августа 2026 года.  
**Статус:** self-hosted FastAPI core готов; active product-notification email flow и provider-backed Google Calendar import реализованы, а verification-email flow и реальная серверная валидация интеграций ещё не готовы к production-включению.

> Основной архитектурный контракт не менялся: Python/FastAPI, PostgreSQL, Redis, RabbitMQ, DDD modular monolith, Transactional Outbox и API `/api/v1` остаются обязательной основой Forma.

## 1. Backend: что готово

Backend находится в `backend/app` и является активным production-контуром. Он реализован как Python/FastAPI modular monolith с выделенными bounded contexts: `identity`, `planning`, `tasks`, `scheduling`, `time_tracking`, `integrations`, `boards`, `ai_planning`, `notifications` и `audit`.

| Область | Готовый функционал | Техническая реализация |
|---|---|---|
| Идентификация и tenancy | Workspace создаётся и проверяется на каждом use case; данные изолированы по `workspace_id` | backend permissions, ownership checks, UUID identifiers |
| Цепочка планирования | Dreams, goals, roadmaps, milestones и actions | REST commands + SQLAlchemy ORM + Alembic schema |
| Задачи и время | Tasks, subtasks, priority, status, estimate, deadlines, manual time entries и timer start/stop | REST API, audit events, linked task/action/milestone checks |
| Календарь | Внутренние typed calendars, events, reschedule, связь с задачами/actions и provider-backed import Google events | normalized `CalendarEvent`, `ExternalEventLink`, sync cursor и persisted success/failed outcome |
| AI | Только `CreateGoal`, `CreateRoadmap`, `CreateTask`, `SuggestCalendarSlots`, `ProjectTaskToCalendar`; preview + явное approval | allow-list, AI plan proposals, idempotent apply, audit |
| Асинхронность | Transactional Outbox, RabbitMQ EventBus adapter, worker receipts, retry/DLQ topology и detached email delivery | outbox publisher, background worker, idempotent consumer receipts, post-commit email task |
| Email notifications | Product notifications после in-app commit для verified и opted-in профилей | Resend env-only adapter, `EmailDeliveryAttempt`, persisted provider result и Russian templates |
| Наблюдаемость | Request/correlation IDs, structured JSON logs, audit trail | middleware, audit records, domain events |
| Безопасность | JWT bearer adapter для production и development-only `X-User-Id` fallback | request context, environment-gated development path |

### Применённые паттерны

| Паттерн | Как применяется в Forma |
|---|---|
| DDD modular monolith | Доменные контексты разделены по ответственности; физическое выделение в микросервисы отложено до измеримой необходимости |
| Transactional Outbox | Доменное изменение и запись события выполняются в одной транзакции PostgreSQL; publisher доставляет событие в RabbitMQ позже |
| EventBus abstraction | RabbitMQ скрыт за интерфейсом, поэтому транспорт можно заменить без изменения application use cases |
| Idempotency key | Все mutating REST commands требуют `Idempotency-Key`, повторный запрос возвращает сохранённый результат |
| Worker receipt | Notification/calendar handlers устраняют повторную обработку одного event ID для конкретного consumer |
| BFF | `/api/v1/bff/workspaces/{workspace_id}/dashboard` агрегирует read model для React |
| Explicit approval | AI не изменяет доменные данные до явного approve; инструментов вне фиксированных пяти нет |

### Проверки backend

Полный изолированный REST scenario прошёл на временной SQLite базе: `workspace → dream → goal → roadmap → milestone → action → task → calendar event → time entry → BFF`. Это **не** заменяет production-проверку PostgreSQL/Redis/RabbitMQ в Docker Compose. Python quality gate проходит: Ruff, strict mypy и 17 pytest tests, включая worker dispatcher success, duplicate delivery, failure → reject without requeue, detached email orchestration, все delivery states (`delivered`, `failed`, `skipped_missing_profile`, `skipped_unverified`, `skipped_opt_out`), mocked Google OAuth callback paths и provider-backed Google event import/cursor outcomes.

## 2. Frontend: что готово

React 19/Vite клиент использует TanStack Query и REST client `client/src/lib/formaApi.ts`; active tRPC transport удалён из runtime. Интерфейс построен как dashboard c постоянной навигацией, responsive layout, shadcn components, Tailwind CSS и Framer Motion.

| Экран/возможность | Готово |
|---|---|
| Onboarding | Создание development workspace и сохранение его ID в local storage |
| Dashboard | Агрегированные goals, tasks, time investment, current focus и notifications через FastAPI BFF |
| Dreams | Создание мечты с визуальной конфигурацией и отображение карточек |
| Goals/Roadmap | Создание цели, roadmap, milestones и actions, визуальное отображение связи |
| Tasks | Создание задач/подзадач, priority, deadline, parent/action/milestone links, completion, timer |
| Calendar | Internal calendars, event creation, filters, Year/Quarter/Month/Week/Day drill-down, breadcrumb, Back navigation и drag reschedule на детальных уровнях |
| Flow Map | Map/Timeline/List проекция реальных связей dream → goal → task |
| AI | Предложение планов и явное подтверждение перед apply |

Весь активный пользовательский интерфейс русифицирован: navigation, onboarding, dashboard, календарные controls/forms, задачи, goals/roadmaps, Flow Map, AI proposal/approval, notifications, domain statuses и error fallback. Внутренние AI command identifiers сохранены в contracts, но в proposal cards отображаются русскоязычные labels.

## 3. Интеграции: честный статус

| Интеграция | Состояние | Что уже есть | Что необходимо завершить до включения |
|---|---|---|---|
| Google Calendar | Partial | OAuth start URL, signed state, callback, code→token exchange, encrypted token storage; Transactional Outbox `CalendarSyncRequested`; provider worker import/upsert в `CalendarEvent` и `ExternalEventLink`, sync cursor и success/failed states | реальная Google credential/redirect validation на self-hosted host, outbound export внутреннего события |
| Email | Partial | in-app notification, active post-commit Resend delivery, verified profile/opt-out gates, `EmailDeliveryAttempt`; Transactional Outbox verification request, signed 24-hour confirmation link и dedicated idempotent verification worker | реальная проверка Resend/domain/HTTPS link на self-hosted host, operational retry policy for failed provider requests |
| RabbitMQ | Production topology готова | EventBus adapter, outbox publisher, worker, DLQ/retry config | запуск и проверка на Docker host |
| Redis | Integrated | workspace locks для AI approval и calendar import; BFF overview cache, post-commit AI invalidation и cache-refresh tests | проверка реального Redis в Docker topology |
| JWT | Adapter готов | bearer token validation и development fallback | реальный issuer/session exchange и production environment setup |

Следовательно, **секреты действительно можно и нужно будет задать только через переменные окружения на вашем сервере**. Email verification flow реализован через outbox и signed link без raw token persistence, но требует реальной проверки Resend и публичного HTTPS origin на self-hosted host. Google Calendar import также требует реальной проверки credentials и redirect URI. Эти ограничения явно сохранены в `todo.md` и `CHANGELOG_AI.md`.

## 4. Deployment готовность

В репозитории подготовлены `deploy/docker-compose.production.yml`, PostgreSQL 16, Redis 7, RabbitMQ 3.13, migrate job, FastAPI SPA/API deployable, outbox worker, events worker, Caddy TLS template, `.env.production.example`, backup script и `SERVER_DEPLOYMENT.md`.

Production topology собирает React через Vite в multi-stage image и копирует static artifact в FastAPI runtime; FastAPI обслуживает SPA fallback и `/api/v1`, а Caddy на хосте завершает TLS. Старый Express/tRPC/Drizzle/MySQL scaffold архивирован в `server/_legacy` и не входит в active runtime, TypeScript/Vitest quality gate или self-hosted production topology.

## 5. Ближайшие обязательные шаги

1. Проверить `deploy/docker-compose.production.yml` на сервере с Docker, PostgreSQL, Redis и RabbitMQ.
2. Проверить реальную отправку/подтверждение verification email через Resend и публичный HTTPS origin.
3. Проверить реальный Google OAuth redirect и import с credentials, заданными через переменные окружения.
4. Реализовать или явно отложить outbound projection внутренних CalendarEvent в Google Calendar.
5. Вынести cross-context ORM checks из router layer в application ports.

Все значимые изменения, риски, quality checks и дальнейшие шаги фиксируются append-only в `CHANGELOG_AI.md`.
