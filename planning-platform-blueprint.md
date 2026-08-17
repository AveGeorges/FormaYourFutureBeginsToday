# Архитектурный blueprint платформы планирования

## 1. Продуктовая идея

Сервис — это не список дел, а **система преобразования намерения в исполнимое действие**. Пользователь движется по цепочке:

> Мечта → визуализация → цель → roadmap → действие → задача → календарный слот → выполненный результат.

Каждый объект может существовать отдельно, но система должна позволять связывать их между собой. Поэтому центральной сущностью продукта становится не `Task`, а **Planning Workspace / пространство планирования**, в котором связаны разные типы объектов.

Первая версия — web-first и персональная. При этом модель данных сразу получает `workspace_id`, роли доступа, владельца и аудит изменений, чтобы позднее добавить совместную работу без переписывания всех агрегатов.

## 2. Основные объекты продукта

| Объект | Назначение | Связи |
|---|---|---|
| Dream | Формулирует желаемое будущее и хранит визуальный образ | Goals, boards, roadmap |
| Goal | Измеримый или качественный результат | Dream, milestones, plans |
| Roadmap | Последовательность этапов достижения цели | Goal, milestones, actions |
| Action | Конкретное действие, которое можно запланировать во времени | Goal, task, calendar event |
| Task | Исполняемая единица работы с дедлайном и прогрессом | Action, subtasks, time entries |
| Calendar | Контейнер событий определённого типа | Events, external calendar connection |
| Calendar Event | Временной слот или событие | Task, Action, external event |
| Board | Визуальный макет для связывания объектов | Любые planning objects |
| Time Entry | Фактически затраченное время | Task, Action, timer session |
| AI Plan | Версионируемый результат работы AI-агента | Dream, Goal, Roadmap, Task, Calendar |

## 3. Рекомендуемая визуализация дел

Основным режимом следует сделать не свободное поле с кругами, а **двухслойную визуализацию Flow Map**.

На верхнем слое отображается временная шкала: день, неделя, месяц, квартал или год. На ней находятся узлы-действия. Размер узла кодирует не только приоритет, но и объём работы; цвет — принадлежность к календарю или цели; форма — тип объекта; обводка — статус. Связи показывают зависимости и цепочки.

На нижнем слое находится компактная панель контекста: выбранная цель, её этапы roadmap, связанные задачи и доступные временные слоты. При выборе узла пользователь не теряет временной контекст и может сразу перенести его на календарь.

| Визуальный параметр | Значение |
|---|---|
| Размер узла | Оценка трудоёмкости, ограниченная диапазоном, чтобы крупные задачи не захватывали экран |
| Цвет | Календарь, область жизни или цель; цвет нельзя использовать как единственный смысловой код |
| Форма | Мечта, цель, этап, действие, задача, событие |
| Обводка | Статус: planned, in progress, blocked, done |
| Положение по X | Временная позиция или дата |
| Положение по Y | Проект, цель, календарь или автоматически рассчитанная дорожка |
| Линия связи | Dependency, parent-child, related-to или projected-to-calendar |
| Толщина линии | Сила зависимости или степень критичности |

Главный UX-принцип: **свободное поле не должно быть единственным способом понять план**. Поэтому для каждого board нужен переключатель `Map / Timeline / List`, а изменения в одном режиме отражаются в остальных. Свободный canvas можно реализовать позднее, но уже сейчас объекты должны иметь координаты, порядок и тип связи.

## 4. Календарная навигация

По умолчанию открывается месяц. Масштабирование должно работать как семантическое изменение плотности, а не как бесконечный zoom-интерфейс. При приближении пользователь переходит к неделе и дню; при отдалении — к кварталу и году. Нажатие на месяц, неделю или день выполняет drill-down, а breadcrumb и кнопка Back возвращают на предыдущий уровень.

Рекомендуемая модель: `Year → Quarter → Month → Week → Day`. У каждого уровня есть собственный layout, но единый диапазон времени и одинаковые операции: создать событие, перетащить, изменить длительность, открыть связанный объект, фильтровать по календарю, цели или статусу.

Внешний календарь не должен быть источником доменной модели. Сервис хранит собственное нормализованное представление события и связывает его с внешним объектом через `ExternalEventLink`. Это позволяет поддерживать внутренний fallback, несколько провайдеров и корректную синхронизацию.

## 5. AI-агент

AI-агент следует проектировать как **планировщика с подтверждением**, а не как компонент, которому сразу разрешено менять данные пользователя.

Поток работы:

1. Пользователь формулирует намерение естественным языком.
2. Агент извлекает структурированную цель, ограничения, предпочтения и недостающие сведения.
3. Агент строит предварительный план: цели, этапы, действия, задачи и предложенные календарные слоты.
4. Система показывает diff-представление: что будет создано, изменено или удалено.
5. Пользователь подтверждает весь план или отдельные операции.
6. Backend применяет команды идемпотентно и сохраняет версию AI Plan.

AI не должен напрямую писать в базу данных. Он вызывает ограниченный набор application commands: `CreateGoal`, `CreateRoadmap`, `CreateTask`, `SuggestCalendarSlots`, `ProjectTaskToCalendar`, `CreateBoardLayout`. Для каждой команды должны существовать схема входных данных, политика доступа, dry-run и журнал результата.

На первом этапе достаточно сценариев: «разложи мечту на цели», «создай план на неделю», «найди свободные слоты для задач», «свяжи задачи с roadmap» и «покажи, почему план перегружен». Автономные советы без явного запроса и автоматическое удаление событий следует отложить.

## 6. MVP первой итерации

В месячный релиз следует включить один законченный пользовательский путь: создать мечту, превратить её в цель и roadmap, получить набор задач, распределить их по календарю и измерять фактически затраченное время.

| Включить в MVP | Отложить после MVP |
|---|---|
| Авторизация и профиль | Полноценная командная коллаборация |
| Внутренние типизированные календари | Сложные права доступа на уровне каждого объекта |
| Подключение одного внешнего календаря | Несколько провайдеров с двусторонней синхронизацией |
| Goals, roadmap, actions, tasks | Расширенный mind-map editor |
| Month/week/day views | Полноценный year heatmap |
| Планирование задач в слоты | Автоматическая оптимизация расписания |
| Таймер и time entries | Сложные аналитические прогнозы |
| List, timeline и Flow Map | Реалистичный бесконечный canvas |
| AI с preview и подтверждением | Полностью автономный агент |
| Уведомления в приложении и email | Платежи с тарифными планами |
| Структурированные логи и аудит | Полный enterprise observability stack |

Платежную систему и отдельный сервис авторизации можно заложить через интерфейсы и контракты, но не следует делать их обязательными для проверки основной ценности продукта. В противном случае месяц уйдёт на инфраструктуру, а ключевой пользовательский сценарий останется недоделанным.

## 7. DDD-контексты

| Bounded Context | Ответственность | Будущий сервис |
|---|---|---|
| Identity & Access | Пользователь, сессии, OAuth, роли, workspace membership | Auth Service |
| Planning | Dream, Goal, Roadmap, Milestone, Action | Planning Service |
| Task Management | Task, Subtask, status, priority, estimates | Task Service |
| Scheduling | Calendar, Event, recurrence, availability | Calendar Service |
| Integrations | OAuth tokens, provider adapters, external links, sync cursors | Integration Service |
| Time Tracking | Timer session, time entry, aggregation | Time Service |
| Visualization | Board, node, edge, layout, projections | Workspace/Board Service |
| Notifications | Notification preferences, templates, delivery attempts | Notification Service |
| AI Planning | Intent, plan proposal, tool calls, approval, versions | AI Orchestrator |
| Billing | Subscription, entitlement, payment status | Billing Service |
| Audit & Observability | Audit records, domain events, correlation data | Audit/Telemetry pipeline |

В модульном монолите каждый контекст должен иметь собственные `domain`, `application`, `infrastructure` и `presentation` пакеты. Модули не должны импортировать ORM-модели друг друга. Связи между контекстами проходят через идентификаторы, application commands и domain events.

## 8. Архитектурный принцип первой версии

Правильная схема для pet-проекта — **модульный монолит с распределёнными границами**, а не набор сетевых микросервисов с первого дня.

Внутри одного deployable приложения находятся отдельные модули. Синхронные операции используют application interfaces. Асинхронные операции публикуют события через абстракцию `EventBus`. Сначала реализация может быть in-process или через таблицу outbox, позднее заменяется на RabbitMQ или Kafka без изменения доменного слоя.

BFF для web-клиента можно сделать отдельным тонким API-слоем поверх application services. API Gateway на первом этапе допустимо представить reverse proxy и единым entry point; сложные маршрутизация, rate limiting и service discovery понадобятся после выделения сервисов.

## 9. Будущие сервисы

Выделение следует начинать с модулей, у которых независимая нагрузка или внешние интеграции: уведомления, интеграции календарей, AI-оркестрация и платежи. Core Planning, Tasks и Scheduling лучше дольше держать вместе, потому что они образуют единый транзакционный пользовательский сценарий.

Рекомендуемый порядок выделения:

`Notifications → Integrations → AI Orchestrator → Billing → Identity → Planning/Tasks/Scheduling`.

Для каждого выделяемого модуля заранее определить владельца данных, публичные команды, публикуемые события, idempotency key, retry policy, dead-letter queue и стратегию совместимости схем.

## 10. Ключевые события

`DreamCreated`, `GoalCreated`, `RoadmapUpdated`, `TaskCreated`, `TaskCompleted`, `CalendarEventScheduled`, `CalendarEventRescheduled`, `ExternalEventImported`, `TimerStarted`, `TimerStopped`, `TimeEntryRecorded`, `AIPlanProposed`, `AIPlanApproved`, `NotificationRequested`, `PaymentStatusChanged`.

Событие сообщает о факте, а не просит другой модуль выполнить действие. Запросы должны идти через команды, например `ScheduleTask` или `SendNotification`. Для надёжности использовать Transactional Outbox: доменная транзакция и запись события фиксируются вместе, после чего relay публикует событие во внешний брокер.

## 11. Предварительный технологический контур

Backend: Python 3.12+, FastAPI, Pydantic v2, SQLAlchemy 2, Alembic, PostgreSQL, Redis для кэша и ephemeral locks. Frontend: React, TypeScript, Vite, TanStack Query, Zustand или Redux Toolkit, библиотека календаря и отдельный слой визуализации Flow Map. Canvas-режим лучше подключать через абстракцию собственного domain adapter, чтобы не связать доменную модель с конкретным редактором.

Для локальной разработки использовать Docker Compose: `web`, `api`, `postgres`, `redis`, `worker`, `mailpit` и при необходимости `rabbitmq`. Kafka для первой версии избыточна: RabbitMQ проще для задач, retry и routing. Однако transport должен быть скрыт за интерфейсом, чтобы позднее заменить брокер.

Кодовая дисциплина: Ruff, mypy, pytest, pre-commit, commit hooks, миграции только через Alembic, OpenAPI contract tests, integration tests для календарной синхронизации и contract tests для событий.

## 12. Главный риск

Главный риск — попытаться одновременно реализовать календарный движок, графовый редактор, микросервисы, платежи и автономного AI-агента. В результате система будет технически впечатляющей, но не даст законченного опыта.

Поэтому критерий готовности месяца должен звучать так: пользователь может пройти путь **«мечта → цель → roadmap → задачи → календарные слоты → таймер → прогресс»**, а AI ускоряет этот путь, но не скрывает изменения и не лишает пользователя контроля.

## 13. Контрактные границы модулей

Каждый модуль должен общаться с соседними модулями через собственные публичные интерфейсы. Например, Scheduling не должен получать объект `Task` из ORM; вместо этого он принимает `TaskProjection` или команду `ScheduleTask` с идентификатором и параметрами времени. Это уменьшает связанность и делает последующее выделение сервиса технически механическим.

| Модуль | Команды | Публикуемые события | Чужие данные, которые допустимо читать |
|---|---|---|---|
| Planning | CreateDream, CreateGoal, AddMilestone, LinkAction | GoalCreated, RoadmapUpdated, ActionCreated | Только identity и workspace policy |
| Tasks | CreateTask, CompleteTask, AddSubtask, SetEstimate | TaskCreated, TaskCompleted, TaskRescheduled | Goal/action IDs через query ports |
| Scheduling | CreateCalendar, ScheduleEvent, MoveEvent, CancelEvent | CalendarEventScheduled, CalendarEventMoved | Task/action summary через projections |
| Time Tracking | StartTimer, StopTimer, AddManualEntry | TimerStarted, TimerStopped, TimeEntryRecorded | Task summary |
| Boards | CreateBoard, AddNode, ConnectNodes, MoveNode | BoardUpdated, ProjectionAdded | Read-only summaries of planning objects |
| Notifications | ConfigurePreference, RequestDelivery | NotificationDelivered, NotificationFailed | User notification preferences |
| AI | CreateProposal, ApproveProposal, RejectProposal | AIPlanProposed, AIPlanApproved | Read models through explicit tools |

## 14. API-слои

Для web-клиента нужен не прямой доступ к доменным модулям, а BFF с ресурсами, ориентированными на экран. Например, экран рабочего пространства может получать агрегированный `WorkspaceOverview`, включающий цели, ближайшие события, просроченные задачи и прогресс. Внутри BFF этот запрос раскладывается на application queries, но наружу клиент получает стабильный контракт.

План API:

| Слой | Назначение | Правило |
|---|---|---|
| API Gateway | TLS termination, CORS, rate limit, request ID, routing | Не содержит бизнес-логики |
| Web BFF | Контракты web-экранов, агрегация, pagination | Не хранит доменные правила |
| Application layer | Commands, queries, authorization checks | Оркестрирует use cases |
| Domain layer | Aggregates, value objects, policies, domain events | Не знает FastAPI, SQLAlchemy и брокер |
| Infrastructure | Repositories, external providers, event transport | Реализует ports |

На старте API Gateway и BFF могут быть двумя слоями одного FastAPI-приложения. Позднее BFF можно отделить, когда появится мобильный клиент с другими экранными контрактами.

## 15. Надёжность операций

Все команды, меняющие состояние, должны принимать `idempotency_key`. Повторный запрос с тем же ключом возвращает тот же результат и не создаёт дубль. Для внешних календарей синхронизация хранит `provider`, `external_calendar_id`, `external_event_id`, `etag`, `last_seen_at`, `sync_cursor` и состояние конфликта.

Для асинхронных обработчиков обязательны retry с экспоненциальной задержкой, ограничение количества попыток и dead-letter queue. Ошибка отправки уведомления не должна откатывать создание задачи. Ошибка синхронизации внешнего календаря должна отображаться пользователю как состояние интеграции, а не превращаться в незаметную потерю данных.

## 16. Безопасность

Внутри каждого use case сначала проверяется принадлежность объекта workspace и затем право действия. Нельзя полагаться только на frontend guards. OAuth-токены внешних календарей хранятся зашифрованными; AI получает только минимально необходимый контекст и не должен видеть секреты интеграций.

Для защиты от prompt injection данные задач, заметок и внешних событий рассматриваются как пользовательский контекст, а не как инструкции. Инструменты AI имеют allow-list, схемы аргументов, ограничения количества операций и обязательное подтверждение для массовых изменений. Все чувствительные действия записываются в audit log.

## 17. Минимальная наблюдаемость

В каждом запросе должны присутствовать `request_id`, `correlation_id`, `user_id` и `workspace_id`. Логи структурируются в JSON и не содержат access token, OAuth secret или полный текст личных заметок без явной необходимости.

Для первой версии достаточно health/readiness endpoints, latency/error metrics, количества задач в очередях, успешности синхронизации и времени ответа AI. Дальше можно добавить OpenTelemetry traces, Prometheus и Grafana.

## 18. План на четыре недели

| Период | Результат |
|---|---|
| Неделя 1 | Репозиторий, Docker Compose, CI, auth stub/OAuth, workspace, PostgreSQL, миграции, базовый BFF, domain module template |
| Неделя 2 | Planning, Tasks, Scheduling, внутренние календари, month/week/day views, связи Goal → Roadmap → Action → Task |
| Неделя 3 | Один внешний календарь, timer/time entries, Flow Map MVP, notification worker, outbox, audit log |
| Неделя 4 | AI proposal flow, подтверждение команд, retries/DLQ, тесты, seed/demo data, документация, deployment и демонстрационный сценарий |

Платежи и отдельный auth-service в месячный план включать как **контрактные заглушки**: интерфейсы, события и entitlement model существуют, но критический путь продукта от них не зависит.

## 19. Предлагаемая структура репозитория

```text
app/
  api/
    gateway.py
    bff/
  modules/
    identity/
      domain/
      application/
      infrastructure/
      presentation/
    planning/
    tasks/
    scheduling/
    integrations/
    time_tracking/
    boards/
    notifications/
    ai_planning/
    billing/
  shared/
    kernel/
    events/
    outbox/
    auth/
    observability/
  workers/
    notification_worker.py
    integration_sync_worker.py
  migrations/
tests/
  unit/
  integration/
  contract/
docker-compose.yml
pyproject.toml
```

Общая папка `shared` должна содержать только действительно технические примитивы: идентификаторы, clock, event envelope, error types, tracing и базовые ports. Она не должна превращаться в свалку доменной логики.

## 20. Архитектурное решение по брокеру

Для первого релиза рекомендую RabbitMQ как транспорт фоновых команд и событий, потому что проекту нужны очереди, routing keys, retry и dead-letter сценарии. Kafka имеет смысл при большом потоке событий, необходимости долгого replay и множестве независимых consumers, но для месячного pet-проекта она заметно увеличит операционную сложность.

Независимо от выбора приложение должно использовать собственный `EventBus` interface и стандартный envelope:

```json
{
  "event_id": "uuid",
  "event_type": "TaskCompleted",
  "event_version": 1,
  "occurred_at": "2026-08-17T12:00:00Z",
  "aggregate_id": "uuid",
  "workspace_id": "uuid",
  "correlation_id": "uuid",
  "payload": {}
}
```

## 21. Критерии качества первой версии

Система считается готовой, если можно создать персональное пространство, подключить календарь, создать мечту, получить из неё цель и roadmap, преобразовать этапы в задачи, запланировать задачи на временную шкалу, запустить таймер, увидеть фактически затраченное время и попросить AI предложить следующий план. При этом повторная доставка события не создаёт дублей, отказ внешнего календаря не уничтожает локальные данные, а каждая AI-операция отображается пользователю до применения.

Следующий практический шаг — не начинать с Kafka и платежей, а зафиксировать доменные контракты и реализовать вертикальный срез `Dream → Goal → Roadmap → Task → Calendar Event → Time Entry`. После его прохождения можно уверенно добавлять инфраструктурные сервисы и выделять модули.
