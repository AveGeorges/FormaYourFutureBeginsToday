CREATE TABLE `actions` (
	`id` int AUTO_INCREMENT NOT NULL,
	`workspaceId` int NOT NULL,
	`goalId` int,
	`milestoneId` int,
	`title` varchar(160) NOT NULL,
	`estimateMinutes` int NOT NULL DEFAULT 30,
	`status` enum('planned','in_progress','completed','blocked') NOT NULL DEFAULT 'planned',
	`createdAt` timestamp NOT NULL DEFAULT (now()),
	`updatedAt` timestamp NOT NULL DEFAULT (now()) ON UPDATE CURRENT_TIMESTAMP,
	CONSTRAINT `actions_id` PRIMARY KEY(`id`)
);
--> statement-breakpoint
CREATE TABLE `aiPlans` (
	`id` int AUTO_INCREMENT NOT NULL,
	`workspaceId` int NOT NULL,
	`intent` text NOT NULL,
	`contextDreamId` int,
	`contextGoalId` int,
	`contextTaskId` int,
	`status` enum('proposed','applied','rejected','failed') NOT NULL DEFAULT 'proposed',
	`proposalJson` text NOT NULL,
	`idempotencyKey` varchar(120),
	`appliedAt` timestamp,
	`createdAt` timestamp NOT NULL DEFAULT (now()),
	CONSTRAINT `aiPlans_id` PRIMARY KEY(`id`),
	CONSTRAINT `ai_plans_idempotency_idx` UNIQUE(`workspaceId`,`idempotencyKey`)
);
--> statement-breakpoint
CREATE TABLE `boardEdges` (
	`id` int AUTO_INCREMENT NOT NULL,
	`workspaceId` int NOT NULL,
	`boardId` int NOT NULL,
	`sourceNodeId` int NOT NULL,
	`targetNodeId` int NOT NULL,
	`edgeType` varchar(40) NOT NULL DEFAULT 'related',
	`createdAt` timestamp NOT NULL DEFAULT (now()),
	CONSTRAINT `boardEdges_id` PRIMARY KEY(`id`)
);
--> statement-breakpoint
CREATE TABLE `boardNodes` (
	`id` int AUTO_INCREMENT NOT NULL,
	`workspaceId` int NOT NULL,
	`boardId` int NOT NULL,
	`objectType` varchar(30) NOT NULL,
	`objectId` int NOT NULL,
	`x` int NOT NULL DEFAULT 0,
	`y` int NOT NULL DEFAULT 0,
	`width` int NOT NULL DEFAULT 180,
	`height` int NOT NULL DEFAULT 110,
	`createdAt` timestamp NOT NULL DEFAULT (now()),
	CONSTRAINT `boardNodes_id` PRIMARY KEY(`id`)
);
--> statement-breakpoint
CREATE TABLE `boards` (
	`id` int AUTO_INCREMENT NOT NULL,
	`workspaceId` int NOT NULL,
	`name` varchar(120) NOT NULL,
	`viewMode` enum('map','timeline','list') NOT NULL DEFAULT 'map',
	`createdAt` timestamp NOT NULL DEFAULT (now()),
	`updatedAt` timestamp NOT NULL DEFAULT (now()) ON UPDATE CURRENT_TIMESTAMP,
	CONSTRAINT `boards_id` PRIMARY KEY(`id`)
);
--> statement-breakpoint
CREATE TABLE `calendarEvents` (
	`id` int AUTO_INCREMENT NOT NULL,
	`workspaceId` int NOT NULL,
	`calendarId` int NOT NULL,
	`taskId` int,
	`actionId` int,
	`title` varchar(160) NOT NULL,
	`startsAt` timestamp NOT NULL,
	`endsAt` timestamp NOT NULL,
	`status` enum('scheduled','completed','cancelled') NOT NULL DEFAULT 'scheduled',
	`createdAt` timestamp NOT NULL DEFAULT (now()),
	`updatedAt` timestamp NOT NULL DEFAULT (now()) ON UPDATE CURRENT_TIMESTAMP,
	CONSTRAINT `calendarEvents_id` PRIMARY KEY(`id`)
);
--> statement-breakpoint
CREATE TABLE `calendars` (
	`id` int AUTO_INCREMENT NOT NULL,
	`workspaceId` int NOT NULL,
	`name` varchar(80) NOT NULL,
	`calendarType` varchar(60) NOT NULL,
	`color` varchar(7) NOT NULL,
	`timezone` varchar(64) NOT NULL DEFAULT 'UTC',
	`provider` varchar(40) NOT NULL DEFAULT 'internal',
	`createdAt` timestamp NOT NULL DEFAULT (now()),
	`updatedAt` timestamp NOT NULL DEFAULT (now()) ON UPDATE CURRENT_TIMESTAMP,
	CONSTRAINT `calendars_id` PRIMARY KEY(`id`)
);
--> statement-breakpoint
CREATE TABLE `dreams` (
	`id` int AUTO_INCREMENT NOT NULL,
	`workspaceId` int NOT NULL,
	`title` varchar(120) NOT NULL,
	`description` text NOT NULL,
	`visualConfig` text NOT NULL,
	`status` enum('active','paused','realized','archived') NOT NULL DEFAULT 'active',
	`createdAt` timestamp NOT NULL DEFAULT (now()),
	`updatedAt` timestamp NOT NULL DEFAULT (now()) ON UPDATE CURRENT_TIMESTAMP,
	CONSTRAINT `dreams_id` PRIMARY KEY(`id`)
);
--> statement-breakpoint
CREATE TABLE `goals` (
	`id` int AUTO_INCREMENT NOT NULL,
	`workspaceId` int NOT NULL,
	`dreamId` int NOT NULL,
	`title` varchar(120) NOT NULL,
	`description` text NOT NULL,
	`status` enum('active','paused','completed','archived') NOT NULL DEFAULT 'active',
	`targetDate` timestamp,
	`createdAt` timestamp NOT NULL DEFAULT (now()),
	`updatedAt` timestamp NOT NULL DEFAULT (now()) ON UPDATE CURRENT_TIMESTAMP,
	CONSTRAINT `goals_id` PRIMARY KEY(`id`)
);
--> statement-breakpoint
CREATE TABLE `milestones` (
	`id` int AUTO_INCREMENT NOT NULL,
	`workspaceId` int NOT NULL,
	`roadmapId` int NOT NULL,
	`title` varchar(160) NOT NULL,
	`position` int NOT NULL DEFAULT 0,
	`status` enum('planned','in_progress','completed','blocked') NOT NULL DEFAULT 'planned',
	`targetDate` timestamp,
	`createdAt` timestamp NOT NULL DEFAULT (now()),
	`updatedAt` timestamp NOT NULL DEFAULT (now()) ON UPDATE CURRENT_TIMESTAMP,
	CONSTRAINT `milestones_id` PRIMARY KEY(`id`)
);
--> statement-breakpoint
CREATE TABLE `notifications` (
	`id` int AUTO_INCREMENT NOT NULL,
	`workspaceId` int NOT NULL,
	`channel` enum('in_app','email') NOT NULL,
	`deliveryStatus` enum('queued','delivered','failed') NOT NULL DEFAULT 'queued',
	`type` varchar(60) NOT NULL,
	`title` varchar(160) NOT NULL,
	`body` text NOT NULL,
	`readAt` timestamp,
	`scheduleCronTaskUid` varchar(65),
	`createdAt` timestamp NOT NULL DEFAULT (now()),
	CONSTRAINT `notifications_id` PRIMARY KEY(`id`)
);
--> statement-breakpoint
CREATE TABLE `roadmaps` (
	`id` int AUTO_INCREMENT NOT NULL,
	`workspaceId` int NOT NULL,
	`goalId` int NOT NULL,
	`title` varchar(120) NOT NULL,
	`status` enum('active','paused','completed','archived') NOT NULL DEFAULT 'active',
	`createdAt` timestamp NOT NULL DEFAULT (now()),
	`updatedAt` timestamp NOT NULL DEFAULT (now()) ON UPDATE CURRENT_TIMESTAMP,
	CONSTRAINT `roadmaps_id` PRIMARY KEY(`id`)
);
--> statement-breakpoint
CREATE TABLE `tasks` (
	`id` int AUTO_INCREMENT NOT NULL,
	`workspaceId` int NOT NULL,
	`actionId` int,
	`milestoneId` int,
	`parentId` int,
	`title` varchar(160) NOT NULL,
	`priority` enum('low','medium','high','critical') NOT NULL DEFAULT 'medium',
	`status` enum('todo','in_progress','blocked','done') NOT NULL DEFAULT 'todo',
	`estimateMinutes` int NOT NULL DEFAULT 30,
	`dueAt` timestamp,
	`createdAt` timestamp NOT NULL DEFAULT (now()),
	`updatedAt` timestamp NOT NULL DEFAULT (now()) ON UPDATE CURRENT_TIMESTAMP,
	CONSTRAINT `tasks_id` PRIMARY KEY(`id`)
);
--> statement-breakpoint
CREATE TABLE `timeEntries` (
	`id` int AUTO_INCREMENT NOT NULL,
	`workspaceId` int NOT NULL,
	`taskId` int NOT NULL,
	`startedAt` timestamp NOT NULL,
	`endedAt` timestamp,
	`durationSeconds` int NOT NULL DEFAULT 0,
	`source` enum('timer','manual') NOT NULL,
	`createdAt` timestamp NOT NULL DEFAULT (now()),
	CONSTRAINT `timeEntries_id` PRIMARY KEY(`id`)
);
--> statement-breakpoint
CREATE TABLE `workspaces` (
	`id` int AUTO_INCREMENT NOT NULL,
	`ownerId` int NOT NULL,
	`name` varchar(120) NOT NULL,
	`timezone` varchar(64) NOT NULL DEFAULT 'UTC',
	`createdAt` timestamp NOT NULL DEFAULT (now()),
	`updatedAt` timestamp NOT NULL DEFAULT (now()) ON UPDATE CURRENT_TIMESTAMP,
	CONSTRAINT `workspaces_id` PRIMARY KEY(`id`),
	CONSTRAINT `workspaces_ownerId_unique` UNIQUE(`ownerId`)
);
--> statement-breakpoint
CREATE INDEX `actions_workspace_idx` ON `actions` (`workspaceId`);--> statement-breakpoint
CREATE INDEX `ai_plans_workspace_idx` ON `aiPlans` (`workspaceId`);--> statement-breakpoint
CREATE INDEX `board_edges_workspace_idx` ON `boardEdges` (`workspaceId`);--> statement-breakpoint
CREATE INDEX `board_edges_board_idx` ON `boardEdges` (`boardId`);--> statement-breakpoint
CREATE INDEX `board_nodes_workspace_idx` ON `boardNodes` (`workspaceId`);--> statement-breakpoint
CREATE INDEX `board_nodes_board_idx` ON `boardNodes` (`boardId`);--> statement-breakpoint
CREATE INDEX `boards_workspace_idx` ON `boards` (`workspaceId`);--> statement-breakpoint
CREATE INDEX `calendar_events_workspace_idx` ON `calendarEvents` (`workspaceId`);--> statement-breakpoint
CREATE INDEX `calendar_events_calendar_idx` ON `calendarEvents` (`calendarId`);--> statement-breakpoint
CREATE INDEX `calendars_workspace_idx` ON `calendars` (`workspaceId`);--> statement-breakpoint
CREATE INDEX `dreams_workspace_idx` ON `dreams` (`workspaceId`);--> statement-breakpoint
CREATE INDEX `goals_workspace_idx` ON `goals` (`workspaceId`);--> statement-breakpoint
CREATE INDEX `goals_dream_idx` ON `goals` (`dreamId`);--> statement-breakpoint
CREATE INDEX `milestones_workspace_idx` ON `milestones` (`workspaceId`);--> statement-breakpoint
CREATE INDEX `milestones_roadmap_idx` ON `milestones` (`roadmapId`);--> statement-breakpoint
CREATE INDEX `notifications_workspace_idx` ON `notifications` (`workspaceId`);--> statement-breakpoint
CREATE INDEX `notifications_schedule_idx` ON `notifications` (`scheduleCronTaskUid`);--> statement-breakpoint
CREATE INDEX `roadmaps_workspace_idx` ON `roadmaps` (`workspaceId`);--> statement-breakpoint
CREATE INDEX `roadmaps_goal_idx` ON `roadmaps` (`goalId`);--> statement-breakpoint
CREATE INDEX `tasks_workspace_idx` ON `tasks` (`workspaceId`);--> statement-breakpoint
CREATE INDEX `tasks_action_idx` ON `tasks` (`actionId`);--> statement-breakpoint
CREATE INDEX `time_entries_workspace_idx` ON `timeEntries` (`workspaceId`);--> statement-breakpoint
CREATE INDEX `time_entries_task_idx` ON `timeEntries` (`taskId`);