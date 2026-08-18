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
current_status: architecture_rebuild_option_A_in_progress
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
current_priority: complete_rest_frontend_parity_and_retire_express_trpc_backend
blocking_issues:
  - current_react_client_still_uses_temporary_trpc_ui_reference_adapter
known_risks:
  - email_notification_records_are_queued_but_no_external_email_provider_is_configured
  - deadline_and_calendar_reminders_require_deployed_heartbeat_setup_before_automatic_delivery
  - external_calendar_oauth_provider_is_not_implemented_in_this_iteration
  - Flow_Map_uses_real_domain_links_but_persisted_custom_board_edges_remain_a_future_iteration
  - FastAPI_worker_topology_requires_persistent_or_always_on_runtime_for_production
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
