BEGIN;

CREATE TABLE alembic_version (
    version_num VARCHAR(32) NOT NULL, 
    CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num)
);

-- Running upgrade  -> 20260818_0001

CREATE TABLE workspaces (
    id UUID NOT NULL, 
    owner_id UUID NOT NULL, 
    name VARCHAR(120) NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    PRIMARY KEY (id)
);

CREATE INDEX ix_workspaces_owner_id ON workspaces (owner_id);

CREATE TABLE workspace_memberships (
    id SERIAL NOT NULL, 
    workspace_id UUID NOT NULL, 
    user_id UUID NOT NULL, 
    role VARCHAR(32) NOT NULL, 
    PRIMARY KEY (id), 
    CONSTRAINT uq_workspace_member UNIQUE (workspace_id, user_id), 
    FOREIGN KEY(workspace_id) REFERENCES workspaces (id) ON DELETE CASCADE
);

CREATE INDEX ix_workspace_memberships_workspace_id ON workspace_memberships (workspace_id);

CREATE INDEX ix_workspace_memberships_user_id ON workspace_memberships (user_id);

CREATE TABLE dreams (
    id UUID NOT NULL, 
    workspace_id UUID NOT NULL, 
    title VARCHAR(200) NOT NULL, 
    description TEXT, 
    visual_config JSONB NOT NULL, 
    status VARCHAR(32) NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(workspace_id) REFERENCES workspaces (id) ON DELETE CASCADE
);

CREATE INDEX ix_dreams_workspace_id ON dreams (workspace_id);

CREATE TABLE goals (
    id UUID NOT NULL, 
    workspace_id UUID NOT NULL, 
    dream_id UUID NOT NULL, 
    title VARCHAR(200) NOT NULL, 
    description TEXT, 
    status VARCHAR(32) NOT NULL, 
    target_date TIMESTAMP WITH TIME ZONE, 
    PRIMARY KEY (id), 
    FOREIGN KEY(workspace_id) REFERENCES workspaces (id) ON DELETE CASCADE, 
    FOREIGN KEY(dream_id) REFERENCES dreams (id) ON DELETE CASCADE
);

CREATE INDEX ix_goals_workspace_id ON goals (workspace_id);

CREATE INDEX ix_goals_dream_id ON goals (dream_id);

CREATE TABLE roadmaps (
    id UUID NOT NULL, 
    workspace_id UUID NOT NULL, 
    goal_id UUID NOT NULL, 
    title VARCHAR(200) NOT NULL, 
    status VARCHAR(32) NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(workspace_id) REFERENCES workspaces (id) ON DELETE CASCADE, 
    FOREIGN KEY(goal_id) REFERENCES goals (id) ON DELETE CASCADE
);

CREATE INDEX ix_roadmaps_workspace_id ON roadmaps (workspace_id);

CREATE INDEX ix_roadmaps_goal_id ON roadmaps (goal_id);

CREATE TABLE milestones (
    id UUID NOT NULL, 
    workspace_id UUID NOT NULL, 
    roadmap_id UUID NOT NULL, 
    title VARCHAR(200) NOT NULL, 
    position INTEGER NOT NULL, 
    status VARCHAR(32) NOT NULL, 
    target_date TIMESTAMP WITH TIME ZONE, 
    PRIMARY KEY (id), 
    FOREIGN KEY(workspace_id) REFERENCES workspaces (id) ON DELETE CASCADE, 
    FOREIGN KEY(roadmap_id) REFERENCES roadmaps (id) ON DELETE CASCADE
);

CREATE INDEX ix_milestones_workspace_id ON milestones (workspace_id);

CREATE INDEX ix_milestones_roadmap_id ON milestones (roadmap_id);

CREATE TABLE actions (
    id UUID NOT NULL, 
    workspace_id UUID NOT NULL, 
    goal_id UUID NOT NULL, 
    milestone_id UUID, 
    title VARCHAR(200) NOT NULL, 
    estimate_minutes INTEGER NOT NULL, 
    status VARCHAR(32) NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(workspace_id) REFERENCES workspaces (id) ON DELETE CASCADE, 
    FOREIGN KEY(goal_id) REFERENCES goals (id) ON DELETE CASCADE, 
    FOREIGN KEY(milestone_id) REFERENCES milestones (id) ON DELETE SET NULL
);

CREATE INDEX ix_actions_workspace_id ON actions (workspace_id);

CREATE INDEX ix_actions_goal_id ON actions (goal_id);

CREATE TABLE tasks (
    id UUID NOT NULL, 
    workspace_id UUID NOT NULL, 
    action_id UUID, 
    milestone_id UUID, 
    parent_id UUID, 
    title VARCHAR(240) NOT NULL, 
    priority VARCHAR(24) NOT NULL, 
    status VARCHAR(24) NOT NULL, 
    estimate_minutes INTEGER NOT NULL, 
    due_at TIMESTAMP WITH TIME ZONE, 
    created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(workspace_id) REFERENCES workspaces (id) ON DELETE CASCADE, 
    FOREIGN KEY(action_id) REFERENCES actions (id) ON DELETE SET NULL, 
    FOREIGN KEY(milestone_id) REFERENCES milestones (id) ON DELETE SET NULL, 
    FOREIGN KEY(parent_id) REFERENCES tasks (id) ON DELETE SET NULL
);

CREATE INDEX ix_tasks_workspace_id ON tasks (workspace_id);

CREATE TABLE calendars (
    id UUID NOT NULL, 
    workspace_id UUID NOT NULL, 
    name VARCHAR(120) NOT NULL, 
    calendar_type VARCHAR(48) NOT NULL, 
    timezone VARCHAR(64) NOT NULL, 
    provider VARCHAR(48) NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(workspace_id) REFERENCES workspaces (id) ON DELETE CASCADE
);

CREATE INDEX ix_calendars_workspace_id ON calendars (workspace_id);

CREATE TABLE calendar_events (
    id UUID NOT NULL, 
    workspace_id UUID NOT NULL, 
    calendar_id UUID NOT NULL, 
    task_id UUID, 
    action_id UUID, 
    title VARCHAR(240) NOT NULL, 
    starts_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    ends_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    status VARCHAR(24) NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(workspace_id) REFERENCES workspaces (id) ON DELETE CASCADE, 
    FOREIGN KEY(calendar_id) REFERENCES calendars (id) ON DELETE CASCADE, 
    FOREIGN KEY(task_id) REFERENCES tasks (id) ON DELETE SET NULL, 
    FOREIGN KEY(action_id) REFERENCES actions (id) ON DELETE SET NULL
);

CREATE INDEX ix_calendar_events_workspace_id ON calendar_events (workspace_id);

CREATE INDEX ix_calendar_events_calendar_id ON calendar_events (calendar_id);

CREATE TABLE external_event_links (
    id UUID NOT NULL, 
    calendar_event_id UUID NOT NULL, 
    provider VARCHAR(48) NOT NULL, 
    external_calendar_id VARCHAR(255) NOT NULL, 
    external_event_id VARCHAR(255) NOT NULL, 
    etag VARCHAR(255), 
    sync_state VARCHAR(32) NOT NULL, 
    last_synced_at TIMESTAMP WITH TIME ZONE, 
    sync_cursor TEXT, 
    PRIMARY KEY (id), 
    FOREIGN KEY(calendar_event_id) REFERENCES calendar_events (id) ON DELETE CASCADE
);

CREATE INDEX ix_external_event_links_calendar_event_id ON external_event_links (calendar_event_id);

CREATE TABLE time_entries (
    id UUID NOT NULL, 
    workspace_id UUID NOT NULL, 
    task_id UUID NOT NULL, 
    started_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    ended_at TIMESTAMP WITH TIME ZONE, 
    duration_seconds INTEGER NOT NULL, 
    source VARCHAR(32) NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(workspace_id) REFERENCES workspaces (id) ON DELETE CASCADE, 
    FOREIGN KEY(task_id) REFERENCES tasks (id) ON DELETE CASCADE
);

CREATE INDEX ix_time_entries_workspace_id ON time_entries (workspace_id);

CREATE INDEX ix_time_entries_task_id ON time_entries (task_id);

CREATE TABLE idempotency_records (
    id SERIAL NOT NULL, 
    user_id UUID NOT NULL, 
    scope VARCHAR(160) NOT NULL, 
    key VARCHAR(255) NOT NULL, 
    response_json JSONB, 
    created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    PRIMARY KEY (id), 
    CONSTRAINT uq_idempotency_scope_key UNIQUE (user_id, scope, key)
);

CREATE INDEX ix_idempotency_records_user_id ON idempotency_records (user_id);

CREATE TABLE outbox_events (
    id UUID NOT NULL, 
    event_type VARCHAR(120) NOT NULL, 
    workspace_id UUID NOT NULL, 
    correlation_id VARCHAR(120) NOT NULL, 
    payload JSONB NOT NULL, 
    occurred_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    published_at TIMESTAMP WITH TIME ZONE, 
    failed_attempts INTEGER NOT NULL, 
    is_dead_lettered BOOLEAN NOT NULL, 
    PRIMARY KEY (id)
);

CREATE INDEX ix_outbox_events_event_type ON outbox_events (event_type);

CREATE INDEX ix_outbox_events_workspace_id ON outbox_events (workspace_id);

CREATE INDEX ix_outbox_events_correlation_id ON outbox_events (correlation_id);

INSERT INTO alembic_version (version_num) VALUES ('20260818_0001') RETURNING alembic_version.version_num;

-- Running upgrade 20260818_0001 -> 20260818_0002

CREATE TABLE boards (
    id UUID NOT NULL, 
    workspace_id UUID NOT NULL, 
    name VARCHAR(160) NOT NULL, 
    view_mode VARCHAR(32) NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(workspace_id) REFERENCES workspaces (id) ON DELETE CASCADE
);

CREATE INDEX ix_boards_workspace_id ON boards (workspace_id);

CREATE TABLE board_nodes (
    id UUID NOT NULL, 
    board_id UUID NOT NULL, 
    object_type VARCHAR(48) NOT NULL, 
    object_id UUID NOT NULL, 
    x INTEGER NOT NULL, 
    y INTEGER NOT NULL, 
    width INTEGER NOT NULL, 
    height INTEGER NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(board_id) REFERENCES boards (id) ON DELETE CASCADE
);

CREATE INDEX ix_board_nodes_board_id ON board_nodes (board_id);

CREATE INDEX ix_board_nodes_object_id ON board_nodes (object_id);

CREATE TABLE board_edges (
    id UUID NOT NULL, 
    board_id UUID NOT NULL, 
    source_node_id UUID NOT NULL, 
    target_node_id UUID NOT NULL, 
    edge_type VARCHAR(48) NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(board_id) REFERENCES boards (id) ON DELETE CASCADE, 
    FOREIGN KEY(source_node_id) REFERENCES board_nodes (id) ON DELETE CASCADE, 
    FOREIGN KEY(target_node_id) REFERENCES board_nodes (id) ON DELETE CASCADE
);

CREATE INDEX ix_board_edges_board_id ON board_edges (board_id);

CREATE INDEX ix_board_edges_source_node_id ON board_edges (source_node_id);

CREATE INDEX ix_board_edges_target_node_id ON board_edges (target_node_id);

CREATE TABLE ai_plans (
    id UUID NOT NULL, 
    workspace_id UUID NOT NULL, 
    prompt TEXT NOT NULL, 
    status VARCHAR(32) NOT NULL, 
    proposal_json JSONB NOT NULL, 
    approval_key VARCHAR(255), 
    approved_at TIMESTAMP WITH TIME ZONE, 
    created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(workspace_id) REFERENCES workspaces (id) ON DELETE CASCADE
);

CREATE INDEX ix_ai_plans_workspace_id ON ai_plans (workspace_id);

CREATE TABLE notifications (
    id UUID NOT NULL, 
    workspace_id UUID NOT NULL, 
    user_id UUID NOT NULL, 
    notification_type VARCHAR(64) NOT NULL, 
    payload JSONB NOT NULL, 
    status VARCHAR(32) NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(workspace_id) REFERENCES workspaces (id) ON DELETE CASCADE
);

CREATE INDEX ix_notifications_workspace_id ON notifications (workspace_id);

CREATE INDEX ix_notifications_user_id ON notifications (user_id);

CREATE TABLE audit_records (
    id UUID NOT NULL, 
    workspace_id UUID NOT NULL, 
    actor_id UUID NOT NULL, 
    action VARCHAR(120) NOT NULL, 
    aggregate_type VARCHAR(80) NOT NULL, 
    aggregate_id UUID NOT NULL, 
    correlation_id VARCHAR(120) NOT NULL, 
    details TEXT, 
    occurred_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    PRIMARY KEY (id)
);

CREATE INDEX ix_audit_records_workspace_id ON audit_records (workspace_id);

CREATE INDEX ix_audit_records_actor_id ON audit_records (actor_id);

CREATE INDEX ix_audit_records_aggregate_id ON audit_records (aggregate_id);

CREATE INDEX ix_audit_records_correlation_id ON audit_records (correlation_id);

UPDATE alembic_version SET version_num='20260818_0002' WHERE alembic_version.version_num = '20260818_0001';

COMMIT;

