# Forma — Project TODO

## Архитектурная пересборка: решение ARCH-001 / вариант A

## Self-hosted server delivery

- [x] Подготовить production Compose topology с FastAPI API, outbox publisher, worker consumers, PostgreSQL, Redis, RabbitMQ, Nginx и persistent volumes.
- [x] Добавить production env template без секретов, безопасные defaults, healthchecks и команды миграции Alembic.
- [x] Добавить internal Nginx reverse proxy со SPA fallback и проксированием `/api/v1` в FastAPI; TLS терминируется внешним Caddy reverse proxy.
- [x] Создать server deployment guide: требования Ubuntu/Docker, первый запуск, обновление, бэкапы, observability и troubleshooting.
- [x] Создать email provider runbook и draft Google Calendar OAuth runbook с явно указанными prerequisite implementation steps.

- [x] Сохранить текущий React-интерфейс как UI-reference и прекратить развитие Express/tRPC/Drizzle backend.
- [x] Создать Python/FastAPI/Pydantic/SQLAlchemy/Alembic backend со структурой DDD bounded contexts.
- [x] Настроить PostgreSQL как единственный source of truth и миграции Alembic вместо MySQL-compatible Drizzle schema.
- [x] Реализовать REST API `/api/v1` с логическими слоями API Gateway и web BFF.
- [x] Добавить `Idempotency-Key` для каждого mutating command и backend workspace ownership/permissions checks.
- [x] Реализовать Transactional Outbox, EventBus abstraction и RabbitMQ transport adapter.
- [x] Добавить Redis для временного состояния, кэша и coordination locks без переноса доменной истины из PostgreSQL.
- [ ] Реализовать worker для уведомлений и календарной синхронизации с идемпотентной обработкой событий.
- [x] Создать normalised CalendarEvent и ExternalEventLink для будущей OAuth-интеграции внешнего календаря.
- [x] Перевести React-клиент с tRPC на versioned REST/BFF contracts без изменения согласованных пользовательских сценариев.
- [x] Настроить JSON logs, request/correlation IDs, audit trail, Ruff, mypy, pytest, pre-commit и contract tests.
- [x] Удалить либо архивировать заменённый Express/tRPC/Drizzle backend после подтверждения parity FastAPI implementation.
- [x] Обновить CHANGELOG_AI.md и подтвердить соответствие итоговой архитектуры документации.
- [x] Добавить production authentication adapter для FastAPI Gateway/BFF вместо development-only trusted `X-User-Id` header.
- [x] Перевести все frontend tRPC-вызовы на REST/BFF client и добавить browser-проверку полного вертикального сценария.
- [x] Настроить development/prod routing React → FastAPI `/api/v1`, CORS и browser smoke test с реальным REST response.
- [x] Добавить development onboarding для создания workspace и передачи `X-User-Id` только в FastAPI development mode; production остаётся только через JWT bearer.
- [ ] Собрать React в FastAPI deployable: FastAPI обслуживает SPA и `/api/v1`, а Express runtime исключён из production path.
- [ ] Провалидировать self-hosted Docker Compose topology FastAPI API и RabbitMQ/Redis worker processes на машине с Docker перед production запуском.
- [ ] Интегрировать Redis в реальный calendar/AI coordination flow и покрыть lock/cache поведение тестами.
- [ ] Реализовать notification worker и calendar sync worker без заглушек: статус обработки, идемпотентность и тесты.
- [x] Расширить audit trail на ключевые mutating commands workspaces, planning, tasks, calendar, time и AI approval.
- [ ] Вынести cross-context ORM checks из FastAPI routers в application ports, чтобы bounded contexts не импортировали ORM-модели друг друга.
- [ ] Реализовать один внешний CalendarProvider OAuth adapter, encrypted token storage и import flow через ExternalEventLink.
- [ ] Подключить базовую email delivery adapter и delivery attempts для deadline/reminder/AI approval notifications.
- [x] Добавить retry/backoff и dead-letter queue для RabbitMQ consumers с тестами повторной доставки.
- [ ] Довести календарный client drill-down до Year → Quarter → Month → Week → Day с breadcrumb и Back через REST/BFF data.
- [ ] Завершить Google Calendar OAuth callback/token exchange и encrypted token storage перед production-включением OAuth runbook.
- [x] Исправить устаревшие числовые преобразования ID в React task/calendar/time формах на UUID-совместимую передачу REST идентификаторов.
- [ ] Реализовать provider-backed calendar sync worker с success/failed статусами и sync cursor; текущий handler только ставит link в очередь.
- [x] Добавить integration/e2e тесты `runner.dispatch_event` для notification, calendar link queueing, duplicate delivery и failure paths.

- [x] Синхронизировать проект с подключённым GitHub-репозиторием и сохранить архитектурные документы в корне проекта.
- [x] Зафиксировать название Forma, позиционирование и девиз в метаданных приложения и стартовом интерфейсе.
- [x] Настроить защищённую модель workspace как строгую границу tenancy для всех пользовательских данных.
- [x] Создать доменную схему и миграции для dreams, goals, roadmaps, milestones, actions, tasks, calendars, calendar events, time entries, boards, nodes, edges, AI plans и уведомлений.
- [x] Реализовать серверные контракты, доступные только владельцу соответствующего workspace.
- [x] Реализовать создание и просмотр dreams с визуальной конфигурацией и статусом.
- [x] Реализовать goals, roadmaps, milestones и actions, связанные с parent dream.
- [x] Реализовать задачи с приоритетом, статусом, оценкой, дедлайном, подзадачами и связью с action или milestone.
- [x] Реализовать внутренние пользовательские typed calendars.
- [x] Реализовать календарные события, проецирование задач в слоты, фильтры и изменение времени перетаскиванием.
- [x] Реализовать Month, Week и Day views с breadcrumb и Back-навигацией для drill-down.
- [x] Реализовать timer и ручные time entries с отображением фактического и оценочного времени.
- [x] Реализовать Flow Map с узлами, зависимостями и переключением Map, Timeline, List.
- [x] Реализовать AI proposal flow со строго фиксированными командами CreateGoal, CreateRoadmap, CreateTask, SuggestCalendarSlots и ProjectTaskToCalendar.
- [x] Исключить применение AI-изменений без явного подтверждения пользователя и обеспечить идемпотентное применение утверждённого плана.
- [x] Реализовать in-app уведомления и безопасную queued-подготовку email-уведомлений для дедлайнов, напоминаний и AI approval prompts; внешний email-провайдер подключается отдельным секретом.
- [x] Создать элегантный, responsive и доступный UI с premium-качеством взаимодействий.
- [x] Добавить Vitest-тесты для tenancy boundary, AI confirmation flow и ключевых доменных операций.
- [x] Проверить приложение в браузере, обновить CHANGELOG_AI.md и сохранить checkpoint первой версии.
- [x] Добавить в UI задач priority, дедлайн, выбор parent task/subtask и связи с action или milestone.
- [x] Показать фактическое и оценочное время с progress indicator на уровне каждой задачи.
- [x] Реализовать Flow Map на вычисляемых связях реальных доменных объектов вместо декоративных линий.
- [x] Добавить Vitest-тесты workspace tenancy boundary и связности ключевых доменных объектов.
- [x] Добавить Vitest-тесты доменной цепочки dream → goal → roadmap → milestone/action → task → calendar event → time entry.
- [x] Добавить серверные тесты отказа cross-workspace access для create/update flows.
- [x] Расширить domain-chain test явным dreams.create перед проверкой пути dream → goal → roadmap → milestone/action → task → calendar event → time entry.
- [x] Добавить cross-workspace denial tests для updateStatus и связанных task/calendar/time create flows.
- [x] Добавить cross-workspace denial tests для tasks.create с чужим action/milestone и time.addManual с чужим task.
- [x] Добавить cross-workspace denial test для tasks.create с чужим milestoneId.
