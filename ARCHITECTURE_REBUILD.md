# Forma — пересборка архитектуры

**Статус:** активна; пользователь подтвердил вариант A 18 августа 2026 года.

Текущий Express/tRPC/Drizzle код — временный UI-reference и не считается соответствующим итоговой архитектуре. Новый backend находится в [`backend/`](./backend) и использует Python, FastAPI, Pydantic, SQLAlchemy, Alembic, PostgreSQL, Redis и RabbitMQ согласно [`MANUS_1_6_IMPLEMENTATION_GUIDE.md`](./MANUS_1_6_IMPLEMENTATION_GUIDE.md).

## Локальный запуск

После установки Docker Engine и Compose:

```bash
docker compose up --build
```

PostgreSQL — единственный источник доменной истины. Redis используется только для кэша и locks, RabbitMQ — транспорт, скрытый за `EventBus`. Каждое доменное изменение должно сохранить событие в transactional outbox в той же PostgreSQL-транзакции.

## Правило миграции

React-клиент сохраняет утверждённые пользовательские сценарии, но после contract parity должен обращаться только к versioned REST/BFF API `/api/v1`. Express/tRPC/Drizzle удаляются или архивируются только после прохождения FastAPI contract tests и полного переноса vertical slice.
