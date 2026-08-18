# CHANGELOG_AI

> Машиночитаемый журнал архитектурных решений и состояния проекта для Manus и других coding-agent моделей.

## FILE_METADATA

```yaml
file: CHANGELOG_AI.md
format_version: 1.0.0
project_codename: planning-platform
product_type: web-first personal planning platform
primary_language: ru
current_iteration: 1
current_status: self_hosted_fastapi_rebuild_core_ready
source_of_truth:
  implementation_guide: MANUS_1_6_IMPLEMENTATION_GUIDE.md
  architecture_blueprint: planning-platform-blueprint.md
  product_vision_target: PRODUCT_VISION_TARGET.md
update_policy: append_only_for_history; update_current_state_block_after_each_milestone
```

## CURRENT_STATE

```yaml
iteration: 1
milestone: ARCH-001_option_A_fastapi_rebuild
status: partial
last_updated: 2026-08-18
implemented: partial
active_vertical_slice: Dream -> Goal -> Roadmap -> Action -> Task -> CalendarEvent -> TimeEntry
current_priority: complete_production_auth_and_external_calendar_oauth_before_public_launch
blocking_issues: []
known_risks:
  - email_notification_records_are_queued_but_no_external_email_provider_is_configured
  - external_calendar_oauth_callback_token_exchange_and_encrypted_token_storage_remain_incomplete
  - production_jwt_issuer_or_oauth_session_exchange_must_be_connected_before_public_launch
  - Flow_Map_uses_real_domain_links_but_persisted_custom_board_edges_remain_a_future_iteration
  - real_postgresql_redis_rabbitmq_stack_must_be_started_on_the_user_server_before_runtime_verification
```

## PRODUCT_CONTEXT

```yaml
product_statement: system_for_turning_intention_into_executable_action
core_chain:
  - Dream
  - Visualization
  - Goal
  - Roadmap
  - Action
  - Task
  - CalendarSlot
  - TimeEntry
  - Progress
first_release:
  platform: web
  user_mode: personal
  collaboration: architecture_ready_but_not_enabled
  external_calendar: one_provider_target
  internal_calendar_fallback: required
  ai_agent: proposal_preview_diff_and_user_approval
future_clients:
  - mobile_app
future_capabilities:
  - collaboration
  - sharing
  - roles
  - offline_sync
  - billing
```

## ARCHITECTURE_DECISIONS

### AD-0001: Modular monolith before physical microservices

```yaml
id: AD-0001
status: accepted
context: project_is_a_one_month_pet_project_with_distributed_system_learning_goal
decision: implement_one_deployable_modular_monolith_with_real_bounded_contexts
consequences:
  positive:
    - faster_vertical_slice_delivery
    - simpler_local_development
    - fewer_network_failure_modes
    - future_service_extraction_remains_possible
  negative:
    - deployment_is_not_yet_physically_distributed
    - module_boundaries_must_be_enforced_by_code_review_and_tests
forbidden_alternative: create_network_microservice_for_every_context_before_core_flow_works
```

### AD-0002: External calendar is an integration, not domain source of truth

```yaml
id: AD-0002
status: accepted
decision: keep_normalized_local_calendar_event_and_external_event_link
required_fields:
  - provider
  - external_calendar_id
  - external_event_id
  - etag_or_version
  - sync_cursor
  - sync_state
fallback: internal_calendar_remains_operational_when_external_provider_fails
```

### AD-0003: AI uses proposals and application commands

```yaml
id: AD-0003
status: accepted
decision: ai_must_not_write_database_directly
flow:
  - user_intent
  - structured_plan_generation
  - validation
  - preview_diff
  - user_approval
  - idempotent_command_application
  - audit_record
allowed_commands:
  - CreateGoal
  - CreateRoadmap
  - CreateTask
  - SuggestCalendarSlots
  - ProjectTaskToCalendar
forbidden_in_iteration_1:
  - autonomous_delete_calendar_event
  - arbitrary_sql
  - unrestricted_tool_execution
```

### AD-0004: RabbitMQ behind EventBus abstraction

```yaml
id: AD-0004
status: accepted
decision: use_transactional_outbox_and_rabbitmq_for_first_iteration
abstraction: EventBus
future_transport_options:
  - Kafka
  - managed_event_bus
requirements:
  - idempotent_consumers
  - retries
  - dead_letter_queue
  - event_versioning
```

### AD-0005: Workspace is the tenancy boundary

```yaml
id: AD-0005
status: accepted
decision: every_user_owned_domain_object_has_workspace_id
future: workspace_membership_and_roles_enable_collaboration
security_rule: every_use_case_must_check_workspace_access_server_side
```

## BOUNDED_CONTEXTS

```yaml
contexts:
  identity:
    responsibility: user_profile_workspace_membership_auth_ports
    future_service: Auth Service
  planning:
    responsibility: dream_goal_roadmap_milestone_action
    future_service: Planning Service
  tasks:
    responsibility: task_subtask_priority_status_estimate
    future_service: Task Service
  scheduling:
    responsibility: calendar_event_recurrence_availability
    future_service: Calendar Service
  integrations:
    responsibility: oauth_provider_adapter_external_links_sync
    future_service: Integration Service
  time_tracking:
    responsibility: timer_session_time_entry_aggregation
    future_service: Time Service
  boards:
    responsibility: board_node_edge_layout_projection
    future_service: Board Service
  notifications:
    responsibility: preferences_templates_delivery_attempts
    future_service: Notification Service
  ai_planning:
    responsibility: intent_plan_proposal_tool_call_approval
    future_service: AI Orchestrator
  billing:
    responsibility: entitlement_contract_only_in_iteration_1
    future_service: Billing Service
  audit:
    responsibility: audit_records_event_metadata_correlation
    future_service: Audit Telemetry Pipeline
```

## DOMAIN_OBJECTS

```yaml
required_objects:
  Workspace: [id, owner_id, name, created_at]
  Dream: [id, workspace_id, title, description, visual_config, status]
  Goal: [id, workspace_id, dream_id, title, description, status, target_date]
  Roadmap: [id, workspace_id, goal_id, title, status]
  Milestone: [id, roadmap_id, title, position, status, target_date]
  Action: [id, workspace_id, goal_id, milestone_id, title, estimate_minutes, status]
  Task: [id, workspace_id, action_id, parent_id, title, priority, status, estimate_minutes, due_at]
  Calendar: [id, workspace_id, name, calendar_type, timezone, provider]
  CalendarEvent: [id, workspace_id, calendar_id, task_id, action_id, starts_at, ends_at, status]
  ExternalEventLink: [id, calendar_event_id, provider, external_calendar_id, external_event_id, etag, sync_state]
  TimeEntry: [id, workspace_id, task_id, started_at, ended_at, duration_seconds, source]
  Board: [id, workspace_id, name, view_mode]
  BoardNode: [id, board_id, object_type, object_id, x, y, width, height]
  BoardEdge: [id, board_id, source_node_id, target_node_id, edge_type]
  AIPlan: [id, workspace_id, prompt, status, proposal_json, approved_at]
```

## EVENT_CATALOG

```yaml
events:
  - DreamCreated
  - GoalCreated
  - RoadmapUpdated
  - ActionCreated
  - TaskCreated
  - TaskCompleted
  - CalendarEventScheduled
  - CalendarEventRescheduled
  - ExternalEventImported
  - TimerStarted
  - TimerStopped
  - TimeEntryRecorded
  - AIPlanProposed
  - AIPlanApproved
  - NotificationRequested
  - PaymentStatusChanged

envelope:
  required_fields:
    - event_id
    - event_type
    - event_version
    - occurred_at
    - aggregate_id
    - workspace_id
    - correlation_id
    - payload
```

## ITERATION_ROADMAP

```yaml
iterations:
  1:
    name: usable_vertical_slice
    status: architecture_rebuild_in_progress
    scope:
      - auth_and_workspace
      - planning_domain
      - tasks
      - internal_calendars
      - one_external_calendar_provider
      - month_week_day_views
      - list_timeline_flow_map_mvp
      - timer_and_time_entries
      - notifications
      - outbox_and_rabbitmq
      - ai_proposal_preview_approval
      - audit_and_structured_logs
  2:
    name: richer_planning_experience
    status: planned
    scope:
      - improved_flow_map_and_canvas
      - recurring_events
      - second_calendar_provider
      - push_notifications
      - richer_analytics
  3:
    name: collaboration
    status: planned
    scope:
      - shared_workspaces
      - invitations
      - roles
      - sharing
      - conflict_resolution
      - mobile_api_contracts
  4:
    name: first_service_extraction
    status: planned
    scope:
      - notification_service
      - integration_service
      - service_owned_data_boundaries
      - centralized_event_broker
  5:
    name: ai_orchestrator
    status: planned
    scope:
      - separate_ai_service
      - plan_optimization
      - retrieval_and_memory
      - approval_policies
  6:
    name: billing
    status: planned
    scope:
      - billing_service
      - subscriptions
      - entitlements
      - usage_limits
  7:
    name: mobile
    status: planned
    scope:
      - mobile_client
      - offline_first_sync
      - device_notifications
  8:
    name: core_extraction
    status: conditional
    scope:
      - identity_service
      - planning_service
      - task_service
      - scheduling_service
    activation_rule: only_after_measured_need_or_explicit_learning_goal
```

## CURRENT_MILESTONE_PLAN

```yaml
milestones:
  - id: M1
    name: repository_foundation
    status: not_started
    deliverables:
      - docker_compose
      - api_web_worker_services
      - postgres_redis_rabbitmq_mailpit
      - ci_lint_format_typecheck
      - migration_baseline
      - module_template
  - id: M2
    name: planning_vertical_slice
    status: not_started
    deliverables:
      - workspace
      - dream
      - goal
      - roadmap
      - milestone
      - action
      - task
      - domain_and_application_tests
  - id: M3
    name: scheduling_and_time
    status: not_started
    deliverables:
      - internal_calendars
      - calendar_events
      - month_week_day_views
      - timer
      - time_entries
  - id: M4
    name: integrations_and_events
    status: not_started
    deliverables:
      - one_external_provider
      - external_event_link
      - sync_worker
      - transactional_outbox
      - event_consumer_deduplication
      - notifications
  - id: M5
    name: ai_and_hardening
    status: not_started
    deliverables:
      - ai_plan
      - structured_output
      - preview_diff
      - approval
      - idempotent_apply
      - audit
      - retries_dlq
      - demo_seed
```

## CHANGE_ENTRY_TEMPLATE

Copy this block for every meaningful change. Never rewrite historical entries; append a new entry.

```yaml
change_id: CHG-YYYYMMDD-NNN
created_at: YYYY-MM-DDThh:mm:ssZ
agent: Manus 1.6
iteration: 1
milestone: M1
status: done | partial | blocked
change_type: feature | bugfix | refactor | architecture | migration | docs | test | security
summary: concise_sentence
reason: why_this_change_exists
files_changed:
  - path/to/file
contracts_changed:
  api: []
  events: []
  database: []
  ai_tools: []
commands_run:
  - command: pytest
    result: passed | failed | not_run
    notes: ""
tests_added: []
migrations:
  created: false
  names: []
breaking_change: false
risks: []
follow_up: []
rollback_notes: ""
```

## CHANGE_HISTORY

```yaml
entries:
  - change_id: CHG-20260817-001
    created_at: 2026-08-17T00:00:00Z
    agent: Manus
    iteration: 0
    milestone: pre_implementation
    status: done
    change_type: architecture
    summary: created_product_and_architecture_blueprint
    reason: establish_product_concept_ux_domain_boundaries_and_future_service_boundaries
    files_changed:
      - planning-platform-blueprint.md
      - planning-architecture.png
    contracts_changed:
      api: []
      events: []
      database: []
      ai_tools: []
    commands_run: []
    tests_added: []
    migrations:
      created: false
      names: []
    breaking_change: false
    risks:
      - implementation_has_not_started
    follow_up:
      - execute_M1_repository_foundation
    rollback_notes: "Architecture-only entry; no runtime rollback required."
  - change_id: CHG-20260817-002
    created_at: 2026-08-17T00:00:00Z
    agent: Manus
    iteration: 0
    milestone: pre_implementation
    status: done
    change_type: docs
    summary: recorded_long_term_product_vision_target
    reason: preserve_original_user_intent_and_product_meaning_across_future_implementations
    files_changed:
      - PRODUCT_VISION_TARGET.md
      - CHANGELOG_AI.md
    contracts_changed:
      api: []
      events: []
      database: []
      ai_tools: []
    commands_run: []
    tests_added: []
    migrations:
      created: false
      names: []
    breaking_change: false
    risks:
      - vision_is_target_state_and_does_not_imply_mvp_scope
    follow_up:
      - keep_product_vision_target_as_semantic_reference
      - keep_implementation_guide_as_execution_reference
      - keep_changelog_as_factual_state_reference
    rollback_notes: "Documentation-only change; no runtime rollback required."
  - change_id: CHG-20260817-003
    created_at: 2026-08-17T00:00:00Z
    agent: Manus
    iteration: 1
    milestone: M1_to_M5
    status: done
    change_type: feature
    summary: implemented_first_working_iteration_of_forma
    reason: deliver_the_core_chain_from_dream_to_goal_roadmap_task_calendar_and_time_tracking
    files_changed:
      - drizzle/schema.ts
      - drizzle/0001_broad_exiles.sql
      - server/forma.ts
      - server/forma.test.ts
      - server/routers.ts
      - client/src/pages/Home.tsx
      - client/src/components/DashboardLayout.tsx
      - client/src/index.css
      - client/src/App.tsx
      - client/index.html
      - todo.md
    contracts_changed:
      api:
        - forma.workspace
        - forma.overview
        - forma.dreams
        - forma.goals
        - forma.roadmaps
        - forma.milestones
        - forma.actions
        - forma.tasks
        - forma.calendars
        - forma.time
        - forma.ai
        - forma.notifications
      events: []
      database:
        - workspaces
        - dreams
        - goals
        - roadmaps
        - milestones
        - actions
        - tasks
        - calendars
        - calendarEvents
        - timeEntries
        - boards
        - boardNodes
        - boardEdges
        - aiPlans
        - notifications
      ai_tools:
        - CreateGoal
        - CreateRoadmap
        - CreateTask
        - SuggestCalendarSlots
        - ProjectTaskToCalendar
    commands_run:
      - command: pnpm drizzle-kit generate
        result: passed
        notes: migration 0001_broad_exiles.sql generated and reviewed
      - command: pnpm check
        result: passed
        notes: TypeScript clean
      - command: pnpm test
        result: passed
        notes: 8 tests passed
    tests_added:
      - fixed_ai_command_whitelist
      - ai_plan_idempotency_state
      - workspace_scope_policy
      - dream_to_goal_to_roadmap_to_action_to_task_to_calendar_to_time_entry
      - cross_workspace_denial_for_goal_task_calendar_and_time_flows
      - email_delivery_provider_fallback
    migrations:
      created: true
      names:
        - 0001_broad_exiles.sql
    breaking_change: false
    risks:
      - email_notifications_are_persisted_as_queued_records_without_external_delivery_provider
      - scheduled_reminders_need_deployment_and_heartbeat_configuration
    follow_up:
      - configure_automatic_notification_delivery_after_deployment
      - implement_external_calendar_provider_adapter
      - configure_external_email_provider_if_transactional_delivery_is_required
    rollback_notes: "Use the first web project checkpoint if a rollback is required."
```

## AI_HANDOFF_PROTOCOL

```yaml
before_work:
  - read_MANUS_1_6_IMPLEMENTATION_GUIDE.md
  - read_CHANGELOG_AI.md
  - inspect_repository
  - inspect_git_status
  - identify_current_milestone
  - identify_unresolved_blockers
rules:
  - do_not_repeat_completed_work_without_verification
  - do_not_change_accepted_architecture_silently
  - do_not_delete_migrations_or_user_data
  - do_not_cross_bounded_context_by_importing_orm_models
  - do_not_allow_ai_direct_database_mutation
  - do_not_claim_done_without_tests
  - update_change_file_after_each_meaningful_change
after_work:
  - run_relevant_tests
  - run_lint_and_typecheck
  - validate_migrations_on_clean_database
  - append_change_entry
  - update_CURRENT_STATE
  - report_next_recommended_step
```

## OPEN_DECISIONS

```yaml
- id: OD-001
  question: which_external_calendar_provider_is_first
  impact: integration_adapter_oauth_scopes_and_sync_behavior
  default_if_unanswered: choose_provider_with_best_documentation_and_test_environment
  status: needs_confirmation
- id: OD-002
  question: authentication_provider_for_MVP
  impact: identity_module_and_frontend_session_flow
  default_if_unanswered: implement local development auth port with replaceable provider adapter
  status: needs_confirmation
- id: OD-003
  question: exact_frontend_canvas_library
  impact: board_interaction_and_bundle_size
  default_if_unanswered: implement List and Timeline first; keep Flow Map behind adapter
  status: needs_confirmation
- id: OD-004
  question: LLM_provider_and_model
  impact: structured_output_tool_calling_cost_and_latency
  default_if_unanswered: implement AI provider port and deterministic fake provider for tests
  status: needs_confirmation
```

## NEXT_ACTION

```yaml
recommended_next_action: review_first_working_iteration_then_configure_deployment_backed_reminders
acceptance:
  - user_can_create_dream_goal_roadmap_task_calendar_block_and_time_entry
  - workspace_scoped_queries_prevent_cross_workspace_access
  - ai_never_applies_changes_without_explicit_approval
  - typecheck_and_tests_pass
  - external_notification_delivery_is_clearly_configured_or_explicitly_deferred
```

## ARCHITECTURE_CONFLICT_2026_08_18

```yaml
conflict_id: ARCH-001
status: resolved_option_A_rebuild_in_place
severity: high
source_of_truth: MANUS_1_6_IMPLEMENTATION_GUIDE.md
required_architecture:
  backend: Python/FastAPI/Pydantic/SQLAlchemy/Alembic
  database: PostgreSQL
  cache: Redis
  broker: RabbitMQ
  async: EventBus abstraction + Transactional Outbox
  workers: notification_and_calendar_sync_worker
actual_implementation:
  backend: Express/tRPC/TypeScript
  database: MySQL-compatible Drizzle schema
  cache: not_implemented
  broker: not_implemented
  outbox: not_implemented
  workers: not_implemented
reason_for_deviation: managed_web_scaffold_contract_was_followed_instead_of_the_mandated_architecture
impact:
  - current_backend_is_not_compliant_with_the_accepted_architecture
  - current_tests_validate_express_trpc_not_fastapi_contracts
  - migration_requires_rebuild_or_parallel_backend_port
options:
  - id: OPTION-A
    title: rebuild_backend_in_place
    risk: high
  - id: OPTION-B
    title: parallel_backend_migration
    risk: medium_high
  - id: OPTION-C
    title: explicitly_approve_temporary_scaffold_exception
    risk: high_architectural_debt
user_selected_option: OPTION-A
implementation_status: FastAPI_PostgreSQL_Redis_RabbitMQ_outbox_workers_and_REST_BFF_foundation_created; frontend_parity_pending
fixed_ai_command_set:
  - CreateGoal
  - CreateRoadmap
  - CreateTask
  - SuggestCalendarSlots
  - ProjectTaskToCalendar
```

## CHANGE_HISTORY_ARCH-001

```yaml
- change_id: CHG-20260818-001
  created_at: 2026-08-18T00:00:00Z
  agent: Manus
  iteration: 1
  milestone: architecture_conflict_detected
  status: awaiting_user_confirmation
  change_type: architecture
  summary: recorded_express_trpc_scaffold_vs_python_fastapi_requirement_conflict
  files_changed:
    - CHANGELOG_AI.md
  breaking_change: pending_decision
  follow_up:
    - obtain_user_choice_before_backend_architecture_changes
  - change_id: CHG-20260818-002
    created_at: 2026-08-18T00:00:00Z
    agent: Manus
    iteration: 1
    milestone: ARCH-001_option_A
    status: partial
    change_type: architecture
    summary: rebuilt_backend_foundation_on_fastapi_postgresql_redis_rabbitmq_outbox_and_workers
    files_changed:
      - backend/
      - docker-compose.yml
      - ARCHITECTURE_REBUILD.md
      - todo.md
      - CHANGELOG_AI.md
    contracts_changed:
      api:
        - /api/v1 REST gateway
        - /api/v1/bff workspace dashboard
      events:
        - transactional outbox envelope
      database:
        - 20260818_0001_initial_schema
        - 20260818_0002_ai_boards_notifications
        - 20260818_0003_worker_receipts
      ai_tools:
        - CreateGoal
        - CreateRoadmap
        - CreateTask
        - SuggestCalendarSlots
        - ProjectTaskToCalendar
    commands_run:
      - command: pytest -q
        result: passed
        notes: 4 FastAPI contract tests passed
      - command: ruff check app tests
        result: passed
        notes: Python lint passed
      - command: mypy app
        result: passed
        notes: strict typing passed
      - command: alembic upgrade head --sql
        result: passed
        notes: PostgreSQL migration SQL generated
    breaking_change: true
    risks:
      - React transport conversion from tRPC to REST/BFF remains incomplete
      - persistent worker hosting remains required before production deployment
    follow_up:
      - complete React REST/BFF conversion
      - run migration against a real PostgreSQL instance
      - archive Express/tRPC/Drizzle after parity verification
```

## ARCHITECTURE_CONFLICT_TODO

- [x] Resolve ARCH-001 with explicit user confirmation before further backend architecture work; user selected OPTION-A.
- [x] Resolve whether CreateBoardLayout is allowed; the fixed five-command AI set is authoritative.

## CHANGE_HISTORY_SELF_HOSTED_DELIVERY

```yaml
- change_id: CHG-20260818-003
  created_at: 2026-08-18T00:00:00Z
  agent: Manus
  iteration: 1
  milestone: ARCH-001_option_A_self_hosted_delivery
  status: partial
  change_type: architecture
  summary: prepared_self_hosted_fastapi_rebuild_with_rest_bff_compose_workers_and_server_runbook
  files_changed:
    - backend/
    - client/src/lib/formaApi.ts
    - client/src/_core/hooks/useAuth.ts
    - client/src/main.tsx
    - deploy/docker-compose.production.yml
    - deploy/frontend.Dockerfile
    - deploy/nginx/default.conf
    - deploy/Caddyfile
    - deploy/backup-postgres.sh
    - .env.production.example
    - SERVER_DEPLOYMENT.md
  contracts_changed:
    api:
      - /api/v1 REST/BFF client transport
      - /api/v1 integrations calendar connect/sync boundary
    events:
      - retry_and_dead_letter_policy
      - idempotent_worker_receipts
    database:
      - alembic_20260818_0001_initial_schema
      - alembic_20260818_0002_ai_boards_notifications
      - alembic_20260818_0003_worker_receipts
    ai_tools:
      - CreateGoal
      - CreateRoadmap
      - CreateTask
      - SuggestCalendarSlots
      - ProjectTaskToCalendar
  commands_run:
    - command: pnpm check && pnpm test
      result: passed
      notes: TypeScript clean; 8 legacy UI-reference tests passed
    - command: ruff check app tests && mypy app && pytest -q
      result: passed
      notes: FastAPI lint/typecheck clean; 5 Python contract tests passed
    - command: alembic upgrade head --sql
      result: passed
      notes: all PostgreSQL migration SQL generated successfully
  migrations:
    created: true
    names:
      - 20260818_0001_initial_schema
      - 20260818_0002_ai_boards_notifications
      - 20260818_0003_worker_receipts
  breaking_change: true
  risks:
    - Docker daemon was unavailable in the build sandbox, so compose runtime must be verified on target server.
    - production authentication issuer and Google OAuth callback/token encryption are deliberate unfinished security integrations.
  follow_up:
    - run deploy/docker-compose.production.yml on target server
    - configure production JWT issuer or OAuth session exchange
    - implement Google OAuth callback and encrypted token storage before enabling external sync
    - archive old Express/tRPC/Drizzle scaffold after runtime parity confirmation
  rollback_notes: use a git tag or the prior checkpoint before applying server migration on a production database.
```

## CHANGE_HISTORY_RUNTIME_SMOKE

```yaml
- change_id: CHG-20260818-004
  created_at: 2026-08-18T00:00:00Z
  agent: Manus
  iteration: 1
  milestone: ARCH-001_runtime_smoke
  status: partial
  change_type: bugfix
  summary: verified_react_to_fastapi_rest_bff_path_and_fixed_uuid_proxy_and_response_default_defects
  files_changed:
    - server/_core/fastapiProxy.ts
    - server/_core/fastapiProxy.test.ts
    - server/_core/index.ts
    - client/src/pages/Home.tsx
    - backend/scripts/bootstrap_sqlite_smoke.py
    - backend/SMOKE_TEST_RESULTS.md
    - backend/tests/test_workers.py
    - backend/app/presentation/planning.py
    - backend/app/presentation/tasks.py
    - backend/app/presentation/scheduling.py
    - todo.md
  contracts_changed:
    api:
      - development_same_origin_proxy_to_/api/v1
      - explicit_canonical_statuses_in_create_responses
    events: []
    database: []
    ai_tools: []
  commands_run:
    - command: full REST vertical slice through time entry and BFF
      result: passed
      notes: temporary SQLite only; production remains PostgreSQL plus Alembic
    - command: browser React onboarding and full BFF slice projection
      result: passed
      notes: verified React -> same-origin proxy -> FastAPI and rendered domain links
    - command: pnpm check && pnpm test
      result: passed
      notes: 10 Vitest tests passed
    - command: ruff check app tests scripts && mypy app && pytest -q
      result: passed
      notes: 6 Python tests passed
  tests_added:
    - development_fastapi_proxy_target_validation
    - notification_and_calendar_sync_handler_receipt_idempotency
  migrations:
    created: false
    names: []
  breaking_change: false
  risks:
    - temporary SQLite smoke setup does not replace Compose validation with PostgreSQL, Redis and RabbitMQ.
    - calendar sync handler queues link state but does not execute provider-backed external sync.
  follow_up:
    - validate Compose topology on target Docker host
    - complete JWT issuer and Google OAuth callback/token encryption before public launch
    - implement provider-backed calendar sync and email delivery adapter
  rollback_notes: revert CHG-20260818-004 files together if the managed development proxy is no longer required.
```

## CHANGE_HISTORY_LEGACY_ARCHIVE

```yaml
- change_id: CHG-20260818-005
  created_at: 2026-08-18T00:00:00Z
  agent: Manus
  iteration: 1
  milestone: ARCH-001_legacy_retirement
  status: done
  change_type: refactor
  summary: archived_express_trpc_drizzle_mysql_scaffold_outside_active_runtime_and_dependency_graph
  files_changed:
    - server/_legacy/
    - server/_core/index.ts
    - shared/types.ts
    - package.json
    - pnpm-lock.yaml
    - tsconfig.json
    - vitest.config.ts
    - todo.md
  contracts_changed:
    api:
      - removed_active_/api/trpc_mount
    events: []
    database:
      - retired_legacy_mysql_drizzle_schema_from_active_source_tree
    ai_tools: []
  commands_run:
    - command: pnpm check && pnpm test
      result: passed
      notes: active TypeScript clean; 2 active proxy regression tests passed
    - command: ruff check app tests scripts && mypy app && pytest -q
      result: passed
      notes: 6 Python tests passed
    - command: alembic upgrade head --sql
      result: passed
      notes: PostgreSQL migration chain unchanged and valid
  migrations:
    created: false
    names: []
  breaking_change: true
  risks:
    - legacy MySQL data is not migrated automatically; self-hosted deployment starts from the FastAPI/Alembic PostgreSQL schema.
  follow_up:
    - validate production Compose on a Docker-capable target host
    - complete external OAuth/provider integrations before enabling them
  rollback_notes: restore the prior checkpoint if legacy scaffold access is required for comparison.
```

## CHANGE_HISTORY_WORKER_CONSUMER_TESTS

```yaml
- change_id: CHG-20260818-006
  created_at: 2026-08-18T00:00:00Z
  agent: Manus
  iteration: 1
  milestone: worker_consumer_quality
  status: partial
  change_type: test
  summary: added_worker_dispatcher_success_duplicate_and_failure_path_coverage
  files_changed:
    - backend/app/workers/runner.py
    - backend/tests/test_workers.py
    - todo.md
  contracts_changed:
    api: []
    events:
      - consumer_failure_rejects_message_without_requeue
    database: []
    ai_tools: []
  commands_run:
    - command: ruff check app tests scripts && mypy app && pytest -q
      result: passed
      notes: 7 Python tests passed
  migrations:
    created: false
    names: []
  breaking_change: false
  risks:
    - actual provider-backed calendar synchronization remains unimplemented.
  follow_up:
    - implement external CalendarProvider OAuth callback/token encryption and sync adapter
  rollback_notes: revert process_message seam and worker tests together if consumer interface changes.
```

## CHANGE_HISTORY_RUSSIAN_UI_AND_INTEGRATION_HANDOFF

```yaml
- change_id: CHG-20260818-007
  created_at: 2026-08-18T00:00:00Z
  agent: Manus
  iteration: 1
  milestone: russian_ui_and_production_handoff
  status: partial
  change_type: feature
  summary: started_active_interface_russian_localization_and_documented_requirement_for_env_configured_integrations
  files_changed:
    - client/src/pages/Home.tsx
    - client/src/components/DashboardLayout.tsx
    - todo.md
    - CHANGELOG_AI.md
  contracts_changed:
    api: []
    events: []
    database: []
    ai_tools: []
  commands_run:
    - command: pnpm check
      result: passed
      notes: Russian UI first-pass compiles successfully
    - command: browser visual review of onboarding
      result: passed
      notes: shell navigation and onboarding display in Russian without layout overflow
  migrations:
    created: false
    names: []
  breaking_change: false
  risks:
    - remaining dashboard dialogs and lower-page informational copy require continued Russian localization.
    - Google Calendar is only an OAuth-start and queued-sync foundation; callback, encrypted tokens and provider operations remain unfinished.
  follow_up:
    - complete all active UI string localization
    - implement complete Google callback/token encryption/provider sync and email adapter using only env configuration
    - extend Russian self-hosted deployment and integration handoff
  rollback_notes: revert the Russian UI string changes if product localization policy changes.
```

## CHANGE_HISTORY_INTEGRATION_SECURITY_FOUNDATION

```yaml
- change_id: CHG-20260818-008
  created_at: 2026-08-18T00:00:00Z
  agent: Manus
  iteration: 1
  milestone: external_integration_security_foundation
  status: partial
  change_type: security
  summary: added_env_only_google_email_configuration_contract_and_fernet_token_encryption_boundary
  files_changed:
    - backend/app/core/config.py
    - backend/app/modules/integrations/infrastructure/token_cipher.py
    - backend/pyproject.toml
    - backend/tests/test_contracts.py
    - .env.production.example
    - deploy/docker-compose.production.yml
    - SERVER_DEPLOYMENT.md
  commands_run:
    - command: ruff check app tests && mypy app && pytest -q
      result: passed
      notes: 8 Python tests passed
  risks:
    - callback/token exchange and provider API sync are not implemented yet; encrypted storage primitive alone does not enable OAuth.
  follow_up:
    - implement Google authorization callback and code exchange
    - implement provider-backed import/export worker and email delivery adapter
  rollback_notes: remove token cipher and env keys together if a future secret manager replaces Fernet-at-rest encryption.
```

## CHANGE_HISTORY_GOOGLE_OAUTH_SIGNED_STATE

```yaml
- change_id: CHG-20260818-009
  created_at: 2026-08-18T00:00:00Z
  agent: Manus
  iteration: 1
  milestone: google_oauth_signed_state
  status: partial
  change_type: security
  summary: replaced_open_calendar_connection_state_with_short_lived_signed_jwt_state
  files_changed:
    - backend/app/presentation/integrations.py
    - backend/tests/test_contracts.py
  commands_run:
    - command: ruff check app tests && mypy app && pytest -q
      result: passed
      notes: 9 Python tests passed
  risks:
    - signed state protects callback correlation but callback code exchange and token persistence are not implemented yet.
  follow_up:
    - validate callback state and exchange Google authorization code using server-side client secret
    - encrypt returned access and refresh tokens in CalendarConnection
  rollback_notes: restore the prior state construction only if replacing the auth state mechanism with server-side Redis state storage.
```

## CHANGE_HISTORY_GOOGLE_OAUTH_CALLBACK

```yaml
- change_id: CHG-20260818-010
  created_at: 2026-08-18T00:00:00Z
  agent: Manus
  iteration: 1
  milestone: google_oauth_callback_and_encrypted_tokens
  status: partial
  change_type: feature
  summary: implemented_signed_state_callback_server_side_code_exchange_and_encrypted_calendar_token_persistence
  files_changed:
    - backend/app/presentation/integrations.py
    - backend/app/modules/integrations/infrastructure/google_calendar.py
  commands_run:
    - command: ruff check app tests && mypy app && pytest -q
      result: passed
      notes: 9 Python tests passed
  risks:
    - callback needs mocked provider integration tests and a deployed HTTPS callback URL before production activation.
    - CalendarProvider list/import/export and worker sync cursor are still unimplemented.
  follow_up:
    - add callback token persistence/invalid state tests
    - implement Google Calendar event import/export and provider-backed sync worker
    - add end-to-end OAuth validation on a Docker host with real Google client credentials
  rollback_notes: revert callback router and provider exchange changes together if changing OAuth library/provider architecture.
```

## CHANGE_HISTORY_EMAIL_DELIVERY_SCHEMA

```yaml
- change_id: CHG-20260818-011
  created_at: 2026-08-18T00:00:00Z
  agent: Manus
  iteration: 1
  milestone: email_delivery_attempt_persistence
  status: partial
  change_type: database
  summary: added_email_delivery_attempt_model_and_postgresql_alembic_migration
  files_changed:
    - backend/app/modules/notifications/infrastructure/models.py
    - backend/alembic/versions/20260818_0004_email_delivery_attempts.py
  commands_run:
    - command: ruff check app tests && mypy app && alembic upgrade head --sql
      result: passed
      notes: PostgreSQL migration chain generates email_delivery_attempts table and index
  risks:
    - no external provider send operation is wired to attempt records yet.
  follow_up:
    - implement Resend HTTP adapter, error mapping and persisted delivery result
    - add integration tests for successful and failed external delivery
  rollback_notes: downgrade revision 20260818_0004 before removing EmailDeliveryAttempt model.
```

## CHANGE_DECISION_SELF_HOSTED_EMAIL_PROFILE

```yaml
- change_id: CHG-20260818-012
  created_at: 2026-08-18T00:00:00Z
  agent: Manus
  iteration: 1
  milestone: self_hosted_email_recipient_identity
  status: approved
  change_type: architecture_decision
  summary: user_approved_self_hosted_profile_with_verified_email_and_notification_preferences
  decision:
    selected_option: self_hosted_user_profile
    rejected_option: jwt_claim_only_recipient_email
    rationale:
      - delivery remains independent of a particular production JWT issuer.
      - Forma obtains a durable source of truth for verified recipient email and notification preferences.
  implementation_scope:
    - UserProfile persisted by user UUID
    - verified email address
    - email notification preference
    - server-side delivery gate requiring verified profile
  risks:
    - initial profile verification flow must be implemented before external email is activated.
  follow_up:
    - add database migration, REST profile commands and verification tokens
    - connect Resend delivery adapter only after verified address check
    - document self-hosted profile and provider configuration
  rollback_notes: remove profile/delivery migration in reverse order if email delivery feature is withdrawn.
```

## CHANGE_HISTORY_SELF_HOSTED_PROFILE_SCHEMA

```yaml
- change_id: CHG-20260818-013
  created_at: 2026-08-18T00:00:00Z
  agent: Manus
  iteration: 1
  milestone: self_hosted_profile_persistence
  status: partial
  change_type: database
  summary: added_user_profiles_and_email_verification_tokens_for_verified_email_delivery_gate
  files_changed:
    - backend/app/modules/identity/infrastructure/models.py
    - backend/alembic/versions/20260818_0005_user_profiles.py
  commands_run:
    - command: ruff check app tests && mypy app && alembic upgrade head --sql
      result: passed
      notes: PostgreSQL migration chain creates user_profiles and email_verification_tokens
  risks:
    - profile REST commands, verification email issue/consume flow and delivery gate remain unimplemented.
  follow_up:
    - implement authenticated profile update and notification preference endpoints
    - issue and consume single-use verification tokens
    - connect verified profile to Resend delivery adapter
  rollback_notes: downgrade revision 20260818_0005 before removing self-hosted profile ORM models.
```

## CHANGE_HISTORY_SELF_HOSTED_PROFILE_API

```yaml
- change_id: CHG-20260818-014
  created_at: 2026-08-18T00:00:00Z
  agent: Manus
  iteration: 1
  milestone: self_hosted_profile_and_verification_api
  status: partial
  change_type: feature
  summary: implemented_authenticated_profile_update_email_preference_and_single_use_verification_token_contract
  files_changed:
    - backend/app/presentation/identity.py
    - backend/pyproject.toml
  commands_run:
    - command: ruff check app tests && mypy app && pytest -q
      result: passed
      notes: 9 Python tests passed after adding explicit email-validator dependency
  risks:
    - issuing token records verification intent but delivery adapter does not yet send the raw token to the profile email.
  follow_up:
    - add profile endpoint integration tests
    - wire issued token to Resend verification message and delivery attempts
    - block notification email when profile is missing, unverified or opted out
  rollback_notes: remove profile routes together with migration 20260818_0005 if self-hosted email profile is removed.
```

## CHANGE_HISTORY_RESEND_PROVIDER_BOUNDARY

```yaml
- change_id: CHG-20260818-015
  created_at: 2026-08-18T00:00:00Z
  agent: Manus
  iteration: 1
  milestone: resend_http_provider_boundary
  status: partial
  change_type: feature
  summary: added_resend_http_adapter_with_env_only_credentials_and_provider_message_id_contract
  files_changed:
    - backend/app/modules/notifications/infrastructure/resend.py
  commands_run:
    - command: ruff check app && mypy app
      result: passed
      notes: 68 source files pass strict type checking
  risks:
    - provider boundary is not yet invoked by notification worker and cannot send verification token until delivery orchestration is wired.
  follow_up:
    - implement verified UserProfile delivery gate and EmailDeliveryAttempt persistence
    - send profile verification and product notification messages through the provider
    - add mocked Resend success/error tests
  rollback_notes: remove isolated provider module if choosing a different transactional email provider.
```

## CHANGE_HISTORY_VERIFIED_PROFILE_DELIVERY_GATE
```yaml
- change_id: CHG-20260818-016
  created_at: 2026-08-18T00:00:00Z
  agent: Manus
  iteration: 1
  milestone: verified_profile_external_delivery_gate
  status: partial
  change_type: feature
  summary: added_email_delivery_worker_with_verified_profile_opt_out_and_persisted_resend_attempt_states
  files_changed:
    - backend/app/workers/email_delivery_worker.py
  commands_run:
    - command: ruff check app && mypy app
      result: passed
      notes: 69 source files pass strict type checking
  delivery_states:
    - delivered
    - failed
    - skipped_missing_profile
    - skipped_unverified
    - skipped_opt_out
  risks:
    - notification worker does not invoke this service yet; no external email is sent by active event processing.
  follow_up:
    - add mocked integration tests for all delivery states
    - route eligible notification IDs to delivery worker without compromising receipt idempotency
    - route verification token to a dedicated email template
  rollback_notes: remove delivery worker service before removing EmailDeliveryAttempt migration.
```

## CHANGE_HISTORY_ACTIVE_EMAIL_ORCHESTRATION

```yaml
- change_id: CHG-20260818-017
  created_at: 2026-08-18T00:00:00Z
  agent: Manus
  iteration: 1
  milestone: active_notification_email_orchestration
  status: done
  change_type: feature
  summary: committed_in_app_notifications_now_trigger_detached_verified_profile_email_delivery_with_mocked_state_coverage
  files_changed:
    - backend/app/workers/notification_worker.py
    - backend/tests/test_workers.py
    - todo.md
  contracts_changed:
    api: []
    events: []
    database: []
    ai_tools: []
  commands_run:
    - command: ruff check app tests && mypy app && pytest -q
      result: passed
      notes: 10 tests passed; Ruff and strict mypy clean across 69 source files
  tests_added:
    - notification worker starts detached delivery only after the in-app notification and worker receipt commit
    - delivered state persists the Resend provider message identifier
    - failed state persists the provider error without changing in-app delivery
    - skipped_missing_profile state is covered
    - skipped_unverified state is covered
    - skipped_opt_out state is covered
  migrations:
    created: false
    names: []
  breaking_change: false
  risks:
    - unexpected failures inside detached delivery are logged and do not reject the already acknowledged RabbitMQ event.
    - provider-backed verification email messages remain a separate, unimplemented flow.
  follow_up:
    - add mocked Google Calendar callback/token exchange integration tests
    - implement provider-backed calendar sync state transitions and cursor
    - complete remaining Russian UI localization
  rollback_notes: remove post-commit task scheduling before removing the existing delivery worker and persisted attempts schema.
```

## CHANGE_HISTORY_EMAIL_DELIVERY_CONTENT_AND_RUNBOOK

```yaml
- change_id: CHG-20260818-018
  created_at: 2026-08-18T00:00:00Z
  agent: Manus
  iteration: 1
  milestone: localized_email_content_and_runbook_sync
  status: partial
  change_type: feature
  summary: replaced_raw_notification_payload_emails_with_russian_event_templates_and_synchronized_self_hosted_email_status_docs
  files_changed:
    - backend/app/workers/email_delivery_worker.py
    - backend/tests/test_workers.py
    - SELF_HOSTED_EMAIL_PROFILE_SETUP_RU.md
    - TECHNICAL_STATUS_RU.md
    - todo.md
  contracts_changed:
    api: []
    events: []
    database: []
    ai_tools: []
  commands_run:
    - command: pnpm check && pnpm test && ruff check app tests && mypy app && pytest -q
      result: passed
      notes: TypeScript check, 2 Vitest tests and 10 Python tests passed; Ruff and strict mypy clean
  tests_added:
    - TaskDueSoon email must use dedicated Russian deadline content instead of fallback or serialized payload
  migrations:
    created: false
    names: []
  breaking_change: false
  risks:
    - email event templates exist for TaskDueSoon and common task/calendar/AI events, but reminder scheduling does not yet emit these event types.
    - verification email remains intentionally deferred until a transaction-safe implementation is designed.
  follow_up:
    - implement transaction-safe verification email through outbox or signed confirmation link
    - complete Russian UI localization and notification BFF presentation copy
    - validate real Resend configuration on the self-hosted Docker topology
  rollback_notes: revert isolated template function and documentation statements; no schema or API contract rollback is required.
```

## CHANGE_HISTORY_REMINDER_TEMPLATE_COVERAGE

```yaml
- change_id: CHG-20260818-019
  created_at: 2026-08-18T00:00:00Z
  agent: Manus
  iteration: 1
  milestone: reminder_template_test_coverage
  status: done
  change_type: test
  summary: added_localized_non_payload_template_contracts_for_task_and_calendar_reminder_event_types
  files_changed:
    - backend/tests/test_workers.py
    - todo.md
  contracts_changed:
    api: []
    events: []
    database: []
    ai_tools: []
  commands_run:
    - command: pnpm check && pnpm test && ruff check app tests && mypy app && pytest -q
      result: passed
      notes: 2 Vitest tests and 12 Python tests passed; Ruff and strict mypy clean
  tests_added:
    - TaskReminder has dedicated Russian subject/body and omits raw payload data
    - CalendarEventReminder has dedicated Russian subject/body and omits raw payload data
  migrations:
    created: false
    names: []
  breaking_change: false
  risks:
    - reminder event templates are ready, while reminder scheduling and event emission remain a separate product capability.
  follow_up:
    - implement transaction-safe verification email flow
    - complete Russian UI localization and notification BFF presentation copy
    - validate deployment on a real Docker host
  rollback_notes: remove only isolated tests; no runtime schema or API rollback required.
```
