# Инструкция для Manus 1.6: реализация Planning Platform

**Версия документа:** 1.0.0  
**Статус:** implementation specification  
**Целевой исполнитель:** Manus 1.6 или совместимая coding-agent модель  
**Основной change-файл:** [`CHANGELOG_AI.md`](./CHANGELOG_AI.md)  
**Исходный архитектурный blueprint:** [`planning-platform-blueprint.md`](./planning-platform-blueprint.md)

---

## 1. Роль и главная задача

Ты реализуешь web-first платформу персонального планирования. Это не обычный to-do list. Продукт преобразует намерение пользователя в исполнимый результат по цепочке:

> Dream → Visualization → Goal → Roadmap → Action → Task → Calendar Slot → Time Entry → Progress.

Твоя задача — сначала создать **работающий вертикальный срез**, а затем расширять его, не разрушая DDD-границы и возможность последующего выделения модулей в распределённые сервисы.

Ты обязан действовать как senior full-stack/backend architect: перед изменением кода изучать текущий репозиторий, читать `CHANGELOG_AI.md`, проверять существующие контракты, не дублировать уже реализованное и после каждой существенной серии изменений обновлять change-файл.

Не пытайся доказать наличие микросервисов количеством контейнеров. Для первой итерации правильный результат — **модульный монолит с контрактами будущих сервисов**, а не набор преждевременно распределённых компонентов.

## 2. Непереговорные архитектурные решения

| Область | Обязательное решение |
|---|---|
| Клиент | Web-first, TypeScript/React; мобильный клиент появится позже |
| Backend | Python, FastAPI, Pydantic, SQLAlchemy, Alembic |
| Хранилище | PostgreSQL как источник истины |
| Кэш и блокировки | Redis, только для временного состояния и кэша |
| Архитектура | Модульный монолит с DDD bounded contexts |
| API | API Gateway и web BFF как логические слои; на старте могут жить в одном deployable приложении |
| Асинхронность | `EventBus` abstraction + Transactional Outbox |
| Брокер | RabbitMQ для первой итерации; транспорт скрыт за интерфейсом для будущей замены |
| Фоновые работы | Worker для уведомлений и синхронизации календаря |
| Календарь | Нормализованное внутреннее событие + `ExternalEventLink`; внешняя система не является источником доменной истины |
| AI | Только через application commands/tools, preview/diff и подтверждение пользователя |
| Безопасность | Проверка workspace ownership/permissions на backend для каждого use case |
| Идемпотентность | Все mutating commands принимают `idempotency_key` |
| Наблюдаемость | Structured JSON logs, request ID, correlation ID, audit trail |
| Качество | Ruff, mypy, pytest, pre-commit, миграции через Alembic, contract tests |

Если новая задача противоречит этой таблице, не меняй решение молча. Зафиксируй конфликт в `CHANGELOG_AI.md`, предложи варианты и запроси подтверждение.

## 3. Что входит в первую итерацию

Первая итерация должна завершить пользовательский сценарий:

1. Пользователь создаёт персональное workspace.
2. Создаёт Dream с названием, описанием, цветовой схемой и необязательными изображениями.
3. Создаёт Goal, связанную с Dream.
4. Создаёт Roadmap с этапами/milestones.
5. Преобразует milestone или Action в Task.
6. Назначает priority, estimate, due date и статус.
7. Проецирует Task/Action в календарный слот.
8. Просматривает месяц, неделю и день.
9. Запускает и останавливает таймер.
10. Получает Time Entry и видит прогресс.
11. Просматривает связанные объекты в List, Timeline и Flow Map.
12. Подключает один внешний календарь через OAuth и импортирует события.
13. Просит AI предложить план и подтверждает его через preview/diff.
14. Получает in-app уведомление и базовое email-уведомление.

Функциональность может быть упрощена визуально, но этот сквозной поток не должен быть заменён набором несвязанных CRUD-экранов.

## 4. Что не должно блокировать первую итерацию

Не трать критический путь на полноценную командную коллаборацию, сложную RBAC-модель на уровне каждого объекта, несколько календарных провайдеров, бесконечный canvas, автоматическую оптимизацию расписания, автономное удаление событий AI, полноценную платёжную систему и физическое выделение всех сервисов.

Для этих возможностей создай расширяемые интерфейсы, идентификаторы, события и контракты. Реализацию перенеси на следующие итерации и обязательно запиши её в change-файле.

## 5. Bounded Contexts и правила модульности

Создай следующие модули:

| Модуль | В первой итерации | Будущий сервис |
|---|---|---|
| `identity` | Профиль, workspace, базовая авторизация | Auth Service |
| `planning` | Dream, Goal, Roadmap, Milestone, Action | Planning Service |
| `tasks` | Task, Subtask, status, priority, estimate | Task Service |
| `scheduling` | Calendar, Event, recurrence, availability | Calendar Service |
| `integrations` | Один календарный provider, OAuth link, sync cursor | Integration Service |
| `time_tracking` | Timer Session, Time Entry, aggregation | Time Service |
| `boards` | Board, nodes, edges, layouts, projections | Board Service |
| `notifications` | Preferences, templates, delivery attempts | Notification Service |
| `ai_planning` | Intent, proposal, tool calls, approval | AI Orchestrator |
| `billing` | Только entitlement interface и contract events | Billing Service |
| `audit` | Audit records, event metadata, correlation | Audit/Telemetry pipeline |

Каждый модуль должен иметь структуру:

```text
module_name/
  domain/
    entities.py
    value_objects.py
    events.py
    policies.py
    repositories.py
  application/
    commands.py
    queries.py
    handlers.py
    dto.py
  infrastructure/
    models.py
    repositories.py
    providers.py
  presentation/
    router.py
    schemas.py
```

Запрещено импортировать ORM-модели одного bounded context из другого. Связи между модулями проходят через entity IDs, DTO, public application ports и domain events. Общий пакет `shared` содержит только технические примитивы: IDs, clock, event envelope, errors, tracing, auth ports и transport ports. Доменную логику в `shared` не помещай.

## 6. Доменная модель первой итерации

Минимальные сущности и обязательные поля:

| Entity | Минимальные поля |
|---|---|
| `Workspace` | `id`, `owner_id`, `name`, `created_at` |
| `Dream` | `id`, `workspace_id`, `title`, `description`, `visual_config`, `status` |
| `Goal` | `id`, `workspace_id`, `dream_id`, `title`, `description`, `status`, `target_date` |
| `Roadmap` | `id`, `workspace_id`, `goal_id`, `title`, `status` |
| `Milestone` | `id`, `roadmap_id`, `title`, `position`, `status`, `target_date` |
| `Action` | `id`, `workspace_id`, `goal_id`, `milestone_id`, `title`, `estimate_minutes`, `status` |
| `Task` | `id`, `workspace_id`, `action_id`, `parent_id`, `title`, `priority`, `status`, `estimate_minutes`, `due_at` |
| `Calendar` | `id`, `workspace_id`, `name`, `calendar_type`, `timezone`, `provider` |
| `CalendarEvent` | `id`, `workspace_id`, `calendar_id`, `task_id`, `action_id`, `starts_at`, `ends_at`, `status` |
| `ExternalEventLink` | `id`, `calendar_event_id`, `provider`, `external_calendar_id`, `external_event_id`, `etag`, `sync_state` |
| `TimeEntry` | `id`, `workspace_id`, `task_id`, `started_at`, `ended_at`, `duration_seconds`, `source` |
| `Board` | `id`, `workspace_id`, `name`, `view_mode` |
| `BoardNode` | `id`, `board_id`, `object_type`, `object_id`, `x`, `y`, `width`, `height` |
| `BoardEdge` | `id`, `board_id`, `source_node_id`, `target_node_id`, `edge_type` |
| `AIPlan` | `id`, `workspace_id`, `prompt`, `status`, `proposal_json`, `approved_at` |

Каждая таблица пользовательского пространства должна иметь `workspace_id`, если это не техническая таблица. Временные значения храни в UTC, отображай с timezone workspace/user. Статусы и типы моделируй через явные enum/value objects, а не произвольные строки.

## 7. События и outbox

Публикуй события-факты:

```text
DreamCreated
GoalCreated
RoadmapUpdated
ActionCreated
TaskCreated
TaskCompleted
CalendarEventScheduled
CalendarEventRescheduled
ExternalEventImported
TimerStarted
TimerStopped
TimeEntryRecorded
AIPlanProposed
AIPlanApproved
NotificationRequested
PaymentStatusChanged
```

Событие не должно быть командой. Команда называется `ScheduleTask`, событие — `CalendarEventScheduled`. Используй envelope:

```json
{
  "event_id": "uuid",
  "event_type": "TaskCompleted",
  "event_version": 1,
  "occurred_at": "ISO-8601 UTC",
  "aggregate_id": "uuid",
  "workspace_id": "uuid",
  "correlation_id": "uuid",
  "payload": {}
}
```

Для каждой транзакции, создающей доменное изменение, запиши событие в outbox в той же транзакции PostgreSQL. Worker публикует неподтверждённые записи в RabbitMQ. Повторная доставка допустима, поэтому consumers обязаны быть идемпотентными. Добавь `processed_events` или эквивалентный механизм deduplication.

## 8. API и application layer

API Gateway отвечает за CORS, request ID, базовый rate limit и маршрутизацию. Бизнес-логика должна находиться в application handlers, а не в FastAPI routers.

BFF предоставляет web-ориентированные read models. Не делай frontend зависимым от внутренних ORM-схем. Используй версионируемые пути API, например `/api/v1/...`.

Минимальные API-группы:

```text
POST   /api/v1/workspaces
GET    /api/v1/workspaces/{workspace_id}/overview
POST   /api/v1/dreams
POST   /api/v1/goals
POST   /api/v1/roadmaps
POST   /api/v1/tasks
PATCH  /api/v1/tasks/{task_id}
POST   /api/v1/calendar-events
PATCH  /api/v1/calendar-events/{event_id}
POST   /api/v1/timers/start
POST   /api/v1/timers/stop
GET    /api/v1/boards/{board_id}/projection
POST   /api/v1/ai/plans
POST   /api/v1/ai/plans/{plan_id}/approve
POST   /api/v1/integrations/calendar/connect
POST   /api/v1/integrations/calendar/sync
```

Все mutating endpoints принимают `Idempotency-Key`. Для ошибок используй единый формат с `code`, `message`, `details`, `request_id`. Добавь OpenAPI schema и contract tests для публичных endpoints.

## 9. AI-агент: строгий режим безопасности

AI не имеет прямого доступа к базе и не выполняет произвольный SQL. Он получает только разрешённые read tools и вызывает только allow-listed application commands:

```text
CreateGoal
CreateRoadmap
CreateTask
SuggestCalendarSlots
ProjectTaskToCalendar
CreateBoardLayout
```

Каждый AI Plan проходит состояния:

```text
draft → generating → proposed → partially_approved/approved → applied
                         ↘ rejected/expired/failed
```

AI обязан возвращать структурированный JSON, валидируемый Pydantic-моделями. Перед применением показывай пользователю diff: создаваемые, изменяемые и потенциально конфликтующие объекты. Прямое удаление календарных событий AI запрещено в первой итерации.

Контекст внешних событий, задач и заметок рассматривай как недоверенные данные, а не как инструкции. Ограничь количество tool calls, добавь timeout, budget и логирование каждого вызова без секретов.

## 10. Интеграция внешнего календаря

Начни с одного provider adapter. Внутри приложения используй интерфейс:

```python
class CalendarProvider(Protocol):
    async def list_events(self, connection: CalendarConnection, window: TimeWindow) -> list[ExternalEvent]: ...
    async def create_event(self, connection: CalendarConnection, event: CalendarEventDraft) -> ExternalEventRef: ...
    async def update_event(self, connection: CalendarConnection, ref: ExternalEventRef, event: CalendarEventDraft) -> None: ...
    async def delete_event(self, connection: CalendarConnection, ref: ExternalEventRef) -> None: ...
```

Синхронизация должна быть повторяемой. Храни provider event ID, etag/version, sync cursor, last sync time и conflict state. Ошибка внешнего API не должна удалять локальное событие. При конфликте сначала оставляй локальные данные и показывай состояние `conflict`, если политика разрешения ещё не задана.

## 11. UX и frontend

Главный экран — workspace dashboard с календарем, ближайшими задачами, прогрессом целей и активным таймером. Календарь по умолчанию открывает месяц. Поддерживай drill-down `Year → Quarter → Month → Week → Day`, breadcrumbs и Back.

Визуализацию дел реализуй как `Flow Map`, а не как единственный бесконечный canvas. Обязательно предоставь режимы `Map`, `Timeline`, `List`. Размер узла отображает ограниченную оценку трудоёмкости, цвет — календарь/область/цель, форма — тип объекта, обводка — статус, линии — тип связи.

Все действия должны быть доступны и через обычный список. Не делай цвет единственным способом передачи статуса. Используй понятные подписи, keyboard-accessible controls и responsive layout, чтобы будущий мобильный клиент мог использовать те же API и доменные контракты.

## 12. Надёжность и безопасность

Для каждого use case сначала проверь, что пользователь имеет доступ к workspace и объекту. Frontend-защита не является механизмом безопасности. Храни OAuth tokens зашифрованными. Не логируй токены, секреты и полный текст приватных заметок.

Добавь:

- request ID и correlation ID;
- `workspace_id` в контекст авторизации;
- idempotency для mutating commands;
- retry с exponential backoff;
- dead-letter queue;
- timeout для внешних API и LLM;
- audit log для чувствительных действий;
- readiness/liveness endpoints;
- structured JSON logs;
- миграции и rollback strategy;
- unit, integration и contract tests.

## 13. Стек и локальный запуск

Используй Docker Compose для локального окружения:

```text
web
api
worker
postgres
redis
rabbitmq
mailpit
```

Рекомендуемый backend stack: FastAPI, Pydantic v2, SQLAlchemy 2, Alembic, PostgreSQL, Redis, RabbitMQ, pytest, Ruff, mypy, pre-commit. Рекомендуемый frontend stack: React, TypeScript, Vite, TanStack Query, Zustand или Redux Toolkit.

Сначала реализуй простой локальный setup с одной командой запуска и seed-данными. Документация должна объяснять переменные окружения, миграции, тесты, запуск worker и подключение внешнего календаря.

## 14. Порядок реализации

### Этап A: основание проекта

Создай репозиторий, Docker Compose, конфигурацию окружений, CI, lint/format/typecheck, базовую авторизацию, workspace и миграции. Проверь, что чистый checkout запускается одной документированной командой.

### Этап B: вертикальный срез домена

Реализуй Planning, Tasks, Scheduling и Time Tracking. Сначала сделай application commands и domain tests, затем repositories, API и frontend. Не начинай с полной админки или сложного canvas.

### Этап C: визуализация и интеграция

Добавь month/week/day, List/Timeline/Flow Map, один внешний calendar provider, `ExternalEventLink`, sync worker, outbox и уведомления.

### Этап D: AI proposal flow

Добавь AI Plan, structured output, read tools, allow-listed commands, preview/diff, approval, idempotent apply и audit trail. AI должен дополнять рабочий пользовательский путь, а не заменять его.

### Этап E: hardening

Добавь retries, DLQ, observability, contract tests, seed/demo scenario, документацию и демонстрационный walkthrough.

## 15. Definition of Done

Фича считается готовой только если:

1. Доменная логика покрыта unit tests.
2. Публичный API имеет схемы, ошибки и contract tests.
3. Проверяется workspace access.
4. Mutating operation идемпотентна.
5. Событие и outbox записываются корректно.
6. Повторная доставка не создаёт дубли.
7. Ошибки внешних API обрабатываются и видны пользователю.
8. Логи содержат request/correlation ID и не содержат секретов.
9. Изменение описано в `CHANGELOG_AI.md`.
10. Документация запуска и миграций обновлена.

## 16. Протокол работы каждого AI-сеанса

Перед началом:

1. Прочитай этот файл.
2. Прочитай `CHANGELOG_AI.md`.
3. Изучи структуру репозитория и незакоммиченные изменения.
4. Определи текущую итерацию, активный milestone и незакрытые блокеры.
5. Не меняй архитектурные решения без записи в change-файл.

Во время работы:

1. Сначала сформулируй небольшой implementation plan.
2. Работай вертикальными срезами.
3. Не смешивай рефакторинг и продуктовую фичу без необходимости.
4. После каждого значимого изменения запускай соответствующие тесты.
5. Не удаляй существующие данные или миграции без явного решения.

После работы:

1. Запусти lint, typecheck, unit/integration tests.
2. Проверь миграции на чистой базе.
3. Обнови `CHANGELOG_AI.md` по шаблону.
4. Укажи изменённые файлы, команды проверки, остаточные риски и следующий шаг.
5. Не утверждай, что фича готова, если она только частично реализована.

## 17. Roadmap следующих итераций

| Итерация | Содержание |
|---|---|
| 2 | Улучшенный Flow Map/canvas, повторяющиеся события, второй календарный provider, push notifications, richer analytics |
| 3 | Командные workspaces, invitations, roles, sharing, conflict resolution, mobile API contracts |
| 4 | Выделение Notification и Integration Service, централизованный event broker, service-owned databases |
| 5 | AI Orchestrator как отдельный сервис, plan optimization, richer memory/retrieval, approval policies |
| 6 | Billing Service, subscriptions, entitlements, usage limits |
| 7 | Мобильное приложение, offline-first sync, device notifications |
| 8 | Выделение Identity и core Planning/Tasks/Scheduling только при подтверждённой необходимости |

Не реализуй следующую итерацию автоматически только потому, что она описана здесь. Сначала обнови roadmap и change-файл с фактическим состоянием.

## 18. Формат отчёта после реализации

Каждый ответ следующему пользователю или ИИ должен иметь структуру:

```text
Status: done | partial | blocked
Iteration: <number>
Milestone: <name>
Summary: <what changed>
Files changed: <paths>
Tests: <commands and results>
Migrations: <yes/no and notes>
Events/API contracts: <changed contracts>
Risks: <remaining risks>
Next recommended step: <one concrete step>
Changelog entry: <CHANGELOG_AI entry id>
```

Пиши кратко, проверяемо и без необоснованных утверждений.
