import { index, int, mysqlEnum, mysqlTable, text, timestamp, uniqueIndex, varchar } from "drizzle-orm/mysql-core";

/**
 * Core user table backing auth flow.
 * Extend this file with additional tables as your product grows.
 * Columns use camelCase to match both database fields and generated types.
 */
export const users = mysqlTable("users", {
  /**
   * Surrogate primary key. Auto-incremented numeric value managed by the database.
   * Use this for relations between tables.
   */
  id: int("id").autoincrement().primaryKey(),
  /** Manus OAuth identifier (openId) returned from the OAuth callback. Unique per user. */
  openId: varchar("openId", { length: 64 }).notNull().unique(),
  name: text("name"),
  email: varchar("email", { length: 320 }),
  loginMethod: varchar("loginMethod", { length: 64 }),
  role: mysqlEnum("role", ["user", "admin"]).default("user").notNull(),
  createdAt: timestamp("createdAt").defaultNow().notNull(),
  updatedAt: timestamp("updatedAt").defaultNow().onUpdateNow().notNull(),
  lastSignedIn: timestamp("lastSignedIn").defaultNow().notNull(),
});

export type User = typeof users.$inferSelect;
export type InsertUser = typeof users.$inferInsert;

export const workspaces = mysqlTable("workspaces", {
  id: int("id").autoincrement().primaryKey(),
  ownerId: int("ownerId").notNull().unique(),
  name: varchar("name", { length: 120 }).notNull(),
  timezone: varchar("timezone", { length: 64 }).notNull().default("UTC"),
  createdAt: timestamp("createdAt").defaultNow().notNull(),
  updatedAt: timestamp("updatedAt").defaultNow().onUpdateNow().notNull(),
});

export const dreams = mysqlTable("dreams", {
  id: int("id").autoincrement().primaryKey(),
  workspaceId: int("workspaceId").notNull(),
  title: varchar("title", { length: 120 }).notNull(),
  description: text("description").notNull(),
  visualConfig: text("visualConfig").notNull(),
  status: mysqlEnum("status", ["active", "paused", "realized", "archived"]).notNull().default("active"),
  createdAt: timestamp("createdAt").defaultNow().notNull(),
  updatedAt: timestamp("updatedAt").defaultNow().onUpdateNow().notNull(),
}, table => [index("dreams_workspace_idx").on(table.workspaceId)]);

export const goals = mysqlTable("goals", {
  id: int("id").autoincrement().primaryKey(),
  workspaceId: int("workspaceId").notNull(),
  dreamId: int("dreamId").notNull(),
  title: varchar("title", { length: 120 }).notNull(),
  description: text("description").notNull(),
  status: mysqlEnum("status", ["active", "paused", "completed", "archived"]).notNull().default("active"),
  targetDate: timestamp("targetDate"),
  createdAt: timestamp("createdAt").defaultNow().notNull(),
  updatedAt: timestamp("updatedAt").defaultNow().onUpdateNow().notNull(),
}, table => [index("goals_workspace_idx").on(table.workspaceId), index("goals_dream_idx").on(table.dreamId)]);

export const roadmaps = mysqlTable("roadmaps", {
  id: int("id").autoincrement().primaryKey(),
  workspaceId: int("workspaceId").notNull(),
  goalId: int("goalId").notNull(),
  title: varchar("title", { length: 120 }).notNull(),
  status: mysqlEnum("status", ["active", "paused", "completed", "archived"]).notNull().default("active"),
  createdAt: timestamp("createdAt").defaultNow().notNull(),
  updatedAt: timestamp("updatedAt").defaultNow().onUpdateNow().notNull(),
}, table => [index("roadmaps_workspace_idx").on(table.workspaceId), index("roadmaps_goal_idx").on(table.goalId)]);

export const milestones = mysqlTable("milestones", {
  id: int("id").autoincrement().primaryKey(),
  workspaceId: int("workspaceId").notNull(),
  roadmapId: int("roadmapId").notNull(),
  title: varchar("title", { length: 160 }).notNull(),
  position: int("position").notNull().default(0),
  status: mysqlEnum("status", ["planned", "in_progress", "completed", "blocked"]).notNull().default("planned"),
  targetDate: timestamp("targetDate"),
  createdAt: timestamp("createdAt").defaultNow().notNull(),
  updatedAt: timestamp("updatedAt").defaultNow().onUpdateNow().notNull(),
}, table => [index("milestones_workspace_idx").on(table.workspaceId), index("milestones_roadmap_idx").on(table.roadmapId)]);

export const actions = mysqlTable("actions", {
  id: int("id").autoincrement().primaryKey(),
  workspaceId: int("workspaceId").notNull(),
  goalId: int("goalId"),
  milestoneId: int("milestoneId"),
  title: varchar("title", { length: 160 }).notNull(),
  estimateMinutes: int("estimateMinutes").notNull().default(30),
  status: mysqlEnum("status", ["planned", "in_progress", "completed", "blocked"]).notNull().default("planned"),
  createdAt: timestamp("createdAt").defaultNow().notNull(),
  updatedAt: timestamp("updatedAt").defaultNow().onUpdateNow().notNull(),
}, table => [index("actions_workspace_idx").on(table.workspaceId)]);

export const tasks = mysqlTable("tasks", {
  id: int("id").autoincrement().primaryKey(),
  workspaceId: int("workspaceId").notNull(),
  actionId: int("actionId"),
  milestoneId: int("milestoneId"),
  parentId: int("parentId"),
  title: varchar("title", { length: 160 }).notNull(),
  priority: mysqlEnum("priority", ["low", "medium", "high", "critical"]).notNull().default("medium"),
  status: mysqlEnum("status", ["todo", "in_progress", "blocked", "done"]).notNull().default("todo"),
  estimateMinutes: int("estimateMinutes").notNull().default(30),
  dueAt: timestamp("dueAt"),
  createdAt: timestamp("createdAt").defaultNow().notNull(),
  updatedAt: timestamp("updatedAt").defaultNow().onUpdateNow().notNull(),
}, table => [index("tasks_workspace_idx").on(table.workspaceId), index("tasks_action_idx").on(table.actionId)]);

export const calendars = mysqlTable("calendars", {
  id: int("id").autoincrement().primaryKey(),
  workspaceId: int("workspaceId").notNull(),
  name: varchar("name", { length: 80 }).notNull(),
  calendarType: varchar("calendarType", { length: 60 }).notNull(),
  color: varchar("color", { length: 7 }).notNull(),
  timezone: varchar("timezone", { length: 64 }).notNull().default("UTC"),
  provider: varchar("provider", { length: 40 }).notNull().default("internal"),
  createdAt: timestamp("createdAt").defaultNow().notNull(),
  updatedAt: timestamp("updatedAt").defaultNow().onUpdateNow().notNull(),
}, table => [index("calendars_workspace_idx").on(table.workspaceId)]);

export const calendarEvents = mysqlTable("calendarEvents", {
  id: int("id").autoincrement().primaryKey(),
  workspaceId: int("workspaceId").notNull(),
  calendarId: int("calendarId").notNull(),
  taskId: int("taskId"),
  actionId: int("actionId"),
  title: varchar("title", { length: 160 }).notNull(),
  startsAt: timestamp("startsAt").notNull(),
  endsAt: timestamp("endsAt").notNull(),
  status: mysqlEnum("status", ["scheduled", "completed", "cancelled"]).notNull().default("scheduled"),
  createdAt: timestamp("createdAt").defaultNow().notNull(),
  updatedAt: timestamp("updatedAt").defaultNow().onUpdateNow().notNull(),
}, table => [index("calendar_events_workspace_idx").on(table.workspaceId), index("calendar_events_calendar_idx").on(table.calendarId)]);

export const timeEntries = mysqlTable("timeEntries", {
  id: int("id").autoincrement().primaryKey(),
  workspaceId: int("workspaceId").notNull(),
  taskId: int("taskId").notNull(),
  startedAt: timestamp("startedAt").notNull(),
  endedAt: timestamp("endedAt"),
  durationSeconds: int("durationSeconds").notNull().default(0),
  source: mysqlEnum("source", ["timer", "manual"]).notNull(),
  createdAt: timestamp("createdAt").defaultNow().notNull(),
}, table => [index("time_entries_workspace_idx").on(table.workspaceId), index("time_entries_task_idx").on(table.taskId)]);

export const boards = mysqlTable("boards", {
  id: int("id").autoincrement().primaryKey(),
  workspaceId: int("workspaceId").notNull(),
  name: varchar("name", { length: 120 }).notNull(),
  viewMode: mysqlEnum("viewMode", ["map", "timeline", "list"]).notNull().default("map"),
  createdAt: timestamp("createdAt").defaultNow().notNull(),
  updatedAt: timestamp("updatedAt").defaultNow().onUpdateNow().notNull(),
}, table => [index("boards_workspace_idx").on(table.workspaceId)]);

export const boardNodes = mysqlTable("boardNodes", {
  id: int("id").autoincrement().primaryKey(),
  workspaceId: int("workspaceId").notNull(),
  boardId: int("boardId").notNull(),
  objectType: varchar("objectType", { length: 30 }).notNull(),
  objectId: int("objectId").notNull(),
  x: int("x").notNull().default(0),
  y: int("y").notNull().default(0),
  width: int("width").notNull().default(180),
  height: int("height").notNull().default(110),
  createdAt: timestamp("createdAt").defaultNow().notNull(),
}, table => [index("board_nodes_workspace_idx").on(table.workspaceId), index("board_nodes_board_idx").on(table.boardId)]);

export const boardEdges = mysqlTable("boardEdges", {
  id: int("id").autoincrement().primaryKey(),
  workspaceId: int("workspaceId").notNull(),
  boardId: int("boardId").notNull(),
  sourceNodeId: int("sourceNodeId").notNull(),
  targetNodeId: int("targetNodeId").notNull(),
  edgeType: varchar("edgeType", { length: 40 }).notNull().default("related"),
  createdAt: timestamp("createdAt").defaultNow().notNull(),
}, table => [index("board_edges_workspace_idx").on(table.workspaceId), index("board_edges_board_idx").on(table.boardId)]);

export const aiPlans = mysqlTable("aiPlans", {
  id: int("id").autoincrement().primaryKey(),
  workspaceId: int("workspaceId").notNull(),
  intent: text("intent").notNull(),
  contextDreamId: int("contextDreamId"),
  contextGoalId: int("contextGoalId"),
  contextTaskId: int("contextTaskId"),
  status: mysqlEnum("status", ["proposed", "applied", "rejected", "failed"]).notNull().default("proposed"),
  proposalJson: text("proposalJson").notNull(),
  idempotencyKey: varchar("idempotencyKey", { length: 120 }),
  appliedAt: timestamp("appliedAt"),
  createdAt: timestamp("createdAt").defaultNow().notNull(),
}, table => [index("ai_plans_workspace_idx").on(table.workspaceId), uniqueIndex("ai_plans_idempotency_idx").on(table.workspaceId, table.idempotencyKey)]);

export const notifications = mysqlTable("notifications", {
  id: int("id").autoincrement().primaryKey(),
  workspaceId: int("workspaceId").notNull(),
  channel: mysqlEnum("channel", ["in_app", "email"]).notNull(),
  deliveryStatus: mysqlEnum("deliveryStatus", ["queued", "delivered", "failed"]).notNull().default("queued"),
  type: varchar("type", { length: 60 }).notNull(),
  title: varchar("title", { length: 160 }).notNull(),
  body: text("body").notNull(),
  readAt: timestamp("readAt"),
  scheduleCronTaskUid: varchar("scheduleCronTaskUid", { length: 65 }),
  createdAt: timestamp("createdAt").defaultNow().notNull(),
}, table => [index("notifications_workspace_idx").on(table.workspaceId), index("notifications_schedule_idx").on(table.scheduleCronTaskUid)]);
