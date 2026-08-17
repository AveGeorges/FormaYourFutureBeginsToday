import { and, desc, eq, isNull } from "drizzle-orm";
import { TRPCError } from "@trpc/server";
import { z } from "zod";
import {
  actions,
  aiPlans,
  boards,
  calendarEvents,
  calendars,
  dreams,
  goals,
  milestones,
  notifications,
  roadmaps,
  tasks,
  timeEntries,
  workspaces,
} from "../drizzle/schema";
import { getDb } from "./db";
import { invokeLLM } from "./_core/llm";
import { protectedProcedure, router } from "./_core/trpc";

const aiCommandNames = [
  "CreateGoal",
  "CreateRoadmap",
  "CreateTask",
  "SuggestCalendarSlots",
  "ProjectTaskToCalendar",
] as const;

const proposalSchema = z.object({
  summary: z.string(),
  commands: z
    .array(
      z.object({
        command: z.enum(aiCommandNames),
        title: z.string(),
        description: z.string().default(""),
        estimateMinutes: z.number().int().min(15).max(480).optional(),
        dayOffset: z.number().int().min(0).max(60).optional(),
      }),
    )
    .max(8),
});

export function validateAIProposal(value: unknown) {
  return proposalSchema.safeParse(value);
}

export function resolvePlanApplicationState(plan: { status: string; appliedAt: Date | null }) {
  if (plan.appliedAt || plan.status === "applied") return "idempotent" as const;
  if (plan.status !== "proposed") return "not_approvable" as const;
  return "ready" as const;
}

const prioritySchema = z.enum(["low", "medium", "high", "critical"]);
const taskStatusSchema = z.enum(["todo", "in_progress", "blocked", "done"]);

async function dbOrThrow() {
  const db = await getDb();
  if (!db) {
    throw new TRPCError({ code: "INTERNAL_SERVER_ERROR", message: "Database is unavailable" });
  }
  return db;
}

async function ensureWorkspace(userId: number) {
  const db = await dbOrThrow();
  const existing = await db.select().from(workspaces).where(eq(workspaces.ownerId, userId)).limit(1);
  if (existing[0]) return existing[0];

  await db.insert(workspaces).values({
    ownerId: userId,
    name: "My Forma space",
    timezone: "UTC",
  });
  const created = await db.select().from(workspaces).where(eq(workspaces.ownerId, userId)).limit(1);
  if (!created[0]) throw new TRPCError({ code: "INTERNAL_SERVER_ERROR", message: "Workspace could not be created" });
  return created[0];
}

export function isWorkspaceScoped(record: { workspaceId: number }, workspaceId: number) {
  return record.workspaceId === workspaceId;
}

async function requireOwnedRecord<T extends { id: any; workspaceId: any }>(
  table: T,
  id: number,
  workspaceId: number,
  label: string,
) {
  const db = await dbOrThrow();
  const record = await db
    .select({ id: table.id, workspaceId: table.workspaceId })
    .from(table as any)
    .where(and(eq(table.id, id), eq(table.workspaceId, workspaceId)))
    .limit(1);
  if (!record[0] || !isWorkspaceScoped(record[0], workspaceId)) {
    throw new TRPCError({ code: "NOT_FOUND", message: `${label} not found in this workspace` });
  }
}

async function ensureDefaultCalendar(workspaceId: number) {
  const db = await dbOrThrow();
  const existing = await db
    .select()
    .from(calendars)
    .where(eq(calendars.workspaceId, workspaceId))
    .limit(1);
  if (existing[0]) return existing[0];

  await db.insert(calendars).values({
    workspaceId,
    name: "Personal rhythm",
    calendarType: "personal",
    color: "#667bff",
    timezone: "UTC",
    provider: "internal",
  });
  const created = await db
    .select()
    .from(calendars)
    .where(eq(calendars.workspaceId, workspaceId))
    .limit(1);
  if (!created[0]) throw new TRPCError({ code: "INTERNAL_SERVER_ERROR", message: "Calendar could not be created" });
  return created[0];
}

function fallbackProposal(intent: string) {
  return {
    summary: "A focused first draft based on your intention. Review every item before applying it.",
    commands: [
      {
        command: "CreateTask" as const,
        title: intent.slice(0, 72) || "Define the next focused step",
        description: "Create one small, observable action that moves the plan forward.",
        estimateMinutes: 45,
        dayOffset: 0,
      },
      {
        command: "SuggestCalendarSlots" as const,
        title: "Protect a focused work block",
        description: "Reserve a calm 45-minute slot before other commitments fill the day.",
        estimateMinutes: 45,
        dayOffset: 1,
      },
    ],
  };
}

async function buildProposal(intent: string) {
  try {
    const response = await invokeLLM({
      messages: [
        {
          role: "system",
          content:
            "You are Forma's planning assistant. Return a concise plan proposal. You may use only these exact commands: CreateGoal, CreateRoadmap, CreateTask, SuggestCalendarSlots, ProjectTaskToCalendar. Never imply that changes have been applied. Keep plans practical and limited to eight commands.",
        },
        { role: "user", content: intent },
      ],
      response_format: {
        type: "json_schema",
        json_schema: {
          name: "forma_plan_proposal",
          strict: true,
          schema: {
            type: "object",
            properties: {
              summary: { type: "string" },
              commands: {
                type: "array",
                items: {
                  type: "object",
                  properties: {
                    command: { type: "string", enum: [...aiCommandNames] },
                    title: { type: "string" },
                    description: { type: "string" },
                    estimateMinutes: { type: "integer" },
                    dayOffset: { type: "integer" },
                  },
                  required: ["command", "title", "description"],
                  additionalProperties: false,
                },
              },
            },
            required: ["summary", "commands"],
            additionalProperties: false,
          },
        },
      },
    });
    const raw = response.choices[0]?.message?.content;
    const parsed = validateAIProposal(typeof raw === "string" ? JSON.parse(raw) : raw);
    return parsed.success ? parsed.data : fallbackProposal(intent);
  } catch {
    return fallbackProposal(intent);
  }
}

export const formaRouter = router({
  workspace: router({
    current: protectedProcedure.query(async ({ ctx }) => ensureWorkspace(ctx.user.id)),
    rename: protectedProcedure
      .input(z.object({ name: z.string().trim().min(2).max(80) }))
      .mutation(async ({ ctx, input }) => {
        const workspace = await ensureWorkspace(ctx.user.id);
        const db = await dbOrThrow();
        await db.update(workspaces).set({ name: input.name }).where(eq(workspaces.id, workspace.id));
        return { ...workspace, name: input.name };
      }),
  }),

  overview: protectedProcedure.query(async ({ ctx }) => {
    const workspace = await ensureWorkspace(ctx.user.id);
    const db = await dbOrThrow();
    const [dreamRows, goalRows, roadmapRows, milestoneRows, actionRows, taskRows, calendarRows, eventRows, entryRows, notificationRows, boardRows, planRows] = await Promise.all([
      db.select().from(dreams).where(eq(dreams.workspaceId, workspace.id)).orderBy(desc(dreams.createdAt)),
      db.select().from(goals).where(eq(goals.workspaceId, workspace.id)).orderBy(desc(goals.createdAt)),
      db.select().from(roadmaps).where(eq(roadmaps.workspaceId, workspace.id)).orderBy(desc(roadmaps.createdAt)),
      db.select().from(milestones).where(eq(milestones.workspaceId, workspace.id)),
      db.select().from(actions).where(eq(actions.workspaceId, workspace.id)),
      db.select().from(tasks).where(eq(tasks.workspaceId, workspace.id)).orderBy(desc(tasks.createdAt)),
      db.select().from(calendars).where(eq(calendars.workspaceId, workspace.id)),
      db.select().from(calendarEvents).where(eq(calendarEvents.workspaceId, workspace.id)).orderBy(desc(calendarEvents.startsAt)),
      db.select().from(timeEntries).where(eq(timeEntries.workspaceId, workspace.id)).orderBy(desc(timeEntries.startedAt)),
      db.select().from(notifications).where(eq(notifications.workspaceId, workspace.id)).orderBy(desc(notifications.createdAt)),
      db.select().from(boards).where(eq(boards.workspaceId, workspace.id)),
      db.select().from(aiPlans).where(eq(aiPlans.workspaceId, workspace.id)).orderBy(desc(aiPlans.createdAt)),
    ]);
    return {
      workspace,
      dreams: dreamRows,
      goals: goalRows,
      roadmaps: roadmapRows,
      milestones: milestoneRows,
      actions: actionRows,
      tasks: taskRows,
      calendars: calendarRows,
      events: eventRows,
      timeEntries: entryRows,
      notifications: notificationRows,
      boards: boardRows,
      aiPlans: planRows,
    };
  }),

  dreams: router({
    create: protectedProcedure
      .input(z.object({ title: z.string().trim().min(2).max(120), description: z.string().max(2000).default(""), color: z.string().regex(/^#[0-9A-Fa-f]{6}$/).default("#7266f0") }))
      .mutation(async ({ ctx, input }) => {
        const workspace = await ensureWorkspace(ctx.user.id);
        const db = await dbOrThrow();
        await db.insert(dreams).values({ workspaceId: workspace.id, title: input.title, description: input.description, visualConfig: JSON.stringify({ color: input.color }), status: "active" });
        return { success: true };
      }),
  }),

  goals: router({
    create: protectedProcedure
      .input(z.object({ dreamId: z.number().int().positive(), title: z.string().trim().min(2).max(120), description: z.string().max(2000).default(""), targetDate: z.date().optional() }))
      .mutation(async ({ ctx, input }) => {
        const workspace = await ensureWorkspace(ctx.user.id);
        await requireOwnedRecord(dreams, input.dreamId, workspace.id, "Dream");
        const db = await dbOrThrow();
        await db.insert(goals).values({ workspaceId: workspace.id, dreamId: input.dreamId, title: input.title, description: input.description, status: "active", targetDate: input.targetDate ?? null });
        return { success: true };
      }),
  }),

  roadmaps: router({
    create: protectedProcedure
      .input(z.object({ goalId: z.number().int().positive(), title: z.string().trim().min(2).max(120) }))
      .mutation(async ({ ctx, input }) => {
        const workspace = await ensureWorkspace(ctx.user.id);
        await requireOwnedRecord(goals, input.goalId, workspace.id, "Goal");
        const db = await dbOrThrow();
        await db.insert(roadmaps).values({ workspaceId: workspace.id, goalId: input.goalId, title: input.title, status: "active" });
        return { success: true };
      }),
  }),

  milestones: router({
    create: protectedProcedure
      .input(z.object({ roadmapId: z.number().int().positive(), title: z.string().trim().min(2).max(160), position: z.number().int().min(0).default(0), targetDate: z.date().optional() }))
      .mutation(async ({ ctx, input }) => {
        const workspace = await ensureWorkspace(ctx.user.id);
        await requireOwnedRecord(roadmaps, input.roadmapId, workspace.id, "Roadmap");
        const db = await dbOrThrow();
        await db.insert(milestones).values({ workspaceId: workspace.id, roadmapId: input.roadmapId, title: input.title, position: input.position, status: "planned", targetDate: input.targetDate ?? null });
        return { success: true };
      }),
  }),

  actions: router({
    create: protectedProcedure
      .input(z.object({ title: z.string().trim().min(2).max(160), goalId: z.number().int().positive().optional(), milestoneId: z.number().int().positive().optional(), estimateMinutes: z.number().int().min(15).max(1440).default(30) }).refine(data => Boolean(data.goalId || data.milestoneId), { message: "An action needs a goal or milestone" }))
      .mutation(async ({ ctx, input }) => {
        const workspace = await ensureWorkspace(ctx.user.id);
        if (input.goalId) await requireOwnedRecord(goals, input.goalId, workspace.id, "Goal");
        if (input.milestoneId) await requireOwnedRecord(milestones, input.milestoneId, workspace.id, "Milestone");
        const db = await dbOrThrow();
        await db.insert(actions).values({ workspaceId: workspace.id, goalId: input.goalId ?? null, milestoneId: input.milestoneId ?? null, title: input.title, estimateMinutes: input.estimateMinutes, status: "planned" });
        return { success: true };
      }),
  }),

  tasks: router({
    create: protectedProcedure
      .input(z.object({ title: z.string().trim().min(2).max(160), priority: prioritySchema.default("medium"), estimateMinutes: z.number().int().min(0).max(1440).default(30), dueAt: z.date().optional(), actionId: z.number().int().positive().optional(), milestoneId: z.number().int().positive().optional(), parentId: z.number().int().positive().optional() }))
      .mutation(async ({ ctx, input }) => {
        const workspace = await ensureWorkspace(ctx.user.id);
        if (input.actionId) await requireOwnedRecord(actions, input.actionId, workspace.id, "Action");
        if (input.milestoneId) await requireOwnedRecord(milestones, input.milestoneId, workspace.id, "Milestone");
        if (input.parentId) await requireOwnedRecord(tasks, input.parentId, workspace.id, "Task");
        const db = await dbOrThrow();
        await db.insert(tasks).values({ workspaceId: workspace.id, actionId: input.actionId ?? null, milestoneId: input.milestoneId ?? null, parentId: input.parentId ?? null, title: input.title, priority: input.priority, status: "todo", estimateMinutes: input.estimateMinutes, dueAt: input.dueAt ?? null });
        if (input.dueAt) {
          const body = `“${input.title}” is due on ${input.dueAt.toLocaleDateString("en")}.`;
          await db.insert(notifications).values([
            { workspaceId: workspace.id, channel: "in_app", deliveryStatus: "queued", title: "Task deadline reminder", body, type: "task_deadline" },
            { workspaceId: workspace.id, channel: "email", deliveryStatus: "queued", title: "Task deadline reminder", body, type: "task_deadline" },
          ]);
        }
        return { success: true };
      }),
    updateStatus: protectedProcedure
      .input(z.object({ taskId: z.number().int().positive(), status: taskStatusSchema }))
      .mutation(async ({ ctx, input }) => {
        const workspace = await ensureWorkspace(ctx.user.id);
        await requireOwnedRecord(tasks, input.taskId, workspace.id, "Task");
        const db = await dbOrThrow();
        await db.update(tasks).set({ status: input.status }).where(eq(tasks.id, input.taskId));
        return { success: true };
      }),
  }),

  calendars: router({
    create: protectedProcedure
      .input(z.object({ name: z.string().trim().min(2).max(80), calendarType: z.string().trim().min(2).max(60), color: z.string().regex(/^#[0-9A-Fa-f]{6}$/).default("#7266f0") }))
      .mutation(async ({ ctx, input }) => {
        const workspace = await ensureWorkspace(ctx.user.id);
        const db = await dbOrThrow();
        await db.insert(calendars).values({ workspaceId: workspace.id, name: input.name, calendarType: input.calendarType, color: input.color, timezone: workspace.timezone, provider: "internal" });
        return { success: true };
      }),
    schedule: protectedProcedure
      .input(z.object({ calendarId: z.number().int().positive().optional(), taskId: z.number().int().positive().optional(), actionId: z.number().int().positive().optional(), title: z.string().trim().min(2).max(160), startsAt: z.date(), endsAt: z.date() }).refine(data => data.endsAt > data.startsAt, { message: "End must be after start" }))
      .mutation(async ({ ctx, input }) => {
        const workspace = await ensureWorkspace(ctx.user.id);
        const calendar = input.calendarId ? (await requireOwnedRecord(calendars, input.calendarId, workspace.id, "Calendar"), input.calendarId) : (await ensureDefaultCalendar(workspace.id)).id;
        if (input.taskId) await requireOwnedRecord(tasks, input.taskId, workspace.id, "Task");
        if (input.actionId) await requireOwnedRecord(actions, input.actionId, workspace.id, "Action");
        const db = await dbOrThrow();
        await db.insert(calendarEvents).values({ workspaceId: workspace.id, calendarId: calendar, taskId: input.taskId ?? null, actionId: input.actionId ?? null, title: input.title, startsAt: input.startsAt, endsAt: input.endsAt, status: "scheduled" });
        await db.insert(notifications).values({ workspaceId: workspace.id, channel: "in_app", deliveryStatus: "queued", title: "Calendar reminder queued", body: `“${input.title}” is scheduled for ${input.startsAt.toLocaleString("en")}.`, type: "calendar_reminder" });
        return { success: true };
      }),
    reschedule: protectedProcedure
      .input(z.object({ eventId: z.number().int().positive(), startsAt: z.date(), endsAt: z.date() }).refine(data => data.endsAt > data.startsAt, { message: "End must be after start" }))
      .mutation(async ({ ctx, input }) => {
        const workspace = await ensureWorkspace(ctx.user.id);
        await requireOwnedRecord(calendarEvents, input.eventId, workspace.id, "Calendar event");
        const db = await dbOrThrow();
        await db.update(calendarEvents).set({ startsAt: input.startsAt, endsAt: input.endsAt, status: "scheduled" }).where(eq(calendarEvents.id, input.eventId));
        return { success: true };
      }),
  }),

  time: router({
    start: protectedProcedure
      .input(z.object({ taskId: z.number().int().positive() }))
      .mutation(async ({ ctx, input }) => {
        const workspace = await ensureWorkspace(ctx.user.id);
        await requireOwnedRecord(tasks, input.taskId, workspace.id, "Task");
        const db = await dbOrThrow();
        const active = await db.select().from(timeEntries).where(and(eq(timeEntries.workspaceId, workspace.id), eq(timeEntries.taskId, input.taskId), isNull(timeEntries.endedAt))).limit(1);
        if (active[0]) return { entry: active[0], alreadyRunning: true };
        await db.insert(timeEntries).values({ workspaceId: workspace.id, taskId: input.taskId, startedAt: new Date(), endedAt: null, durationSeconds: 0, source: "timer" });
        const entry = await db.select().from(timeEntries).where(and(eq(timeEntries.workspaceId, workspace.id), eq(timeEntries.taskId, input.taskId), isNull(timeEntries.endedAt))).limit(1);
        return { entry: entry[0], alreadyRunning: false };
      }),
    stop: protectedProcedure
      .input(z.object({ taskId: z.number().int().positive() }))
      .mutation(async ({ ctx, input }) => {
        const workspace = await ensureWorkspace(ctx.user.id);
        await requireOwnedRecord(tasks, input.taskId, workspace.id, "Task");
        const db = await dbOrThrow();
        const active = await db.select().from(timeEntries).where(and(eq(timeEntries.workspaceId, workspace.id), eq(timeEntries.taskId, input.taskId), isNull(timeEntries.endedAt))).limit(1);
        if (!active[0]) return { stopped: false };
        const endedAt = new Date();
        const durationSeconds = Math.max(1, Math.round((endedAt.getTime() - active[0].startedAt.getTime()) / 1000));
        await db.update(timeEntries).set({ endedAt, durationSeconds }).where(eq(timeEntries.id, active[0].id));
        return { stopped: true, durationSeconds };
      }),
    addManual: protectedProcedure
      .input(z.object({ taskId: z.number().int().positive(), startedAt: z.date(), endedAt: z.date() }).refine(data => data.endedAt > data.startedAt, { message: "End must be after start" }))
      .mutation(async ({ ctx, input }) => {
        const workspace = await ensureWorkspace(ctx.user.id);
        await requireOwnedRecord(tasks, input.taskId, workspace.id, "Task");
        const db = await dbOrThrow();
        const durationSeconds = Math.round((input.endedAt.getTime() - input.startedAt.getTime()) / 1000);
        await db.insert(timeEntries).values({ workspaceId: workspace.id, taskId: input.taskId, startedAt: input.startedAt, endedAt: input.endedAt, durationSeconds, source: "manual" });
        return { success: true };
      }),
  }),

  ai: router({
    propose: protectedProcedure
      .input(z.object({ intent: z.string().trim().min(8).max(3000), dreamId: z.number().int().positive().optional(), goalId: z.number().int().positive().optional(), taskId: z.number().int().positive().optional() }))
      .mutation(async ({ ctx, input }) => {
        const workspace = await ensureWorkspace(ctx.user.id);
        if (input.dreamId) await requireOwnedRecord(dreams, input.dreamId, workspace.id, "Dream");
        if (input.goalId) await requireOwnedRecord(goals, input.goalId, workspace.id, "Goal");
        if (input.taskId) await requireOwnedRecord(tasks, input.taskId, workspace.id, "Task");
        const proposal = await buildProposal(input.intent);
        const db = await dbOrThrow();
        await db.insert(aiPlans).values({ workspaceId: workspace.id, intent: input.intent, contextDreamId: input.dreamId ?? null, contextGoalId: input.goalId ?? null, contextTaskId: input.taskId ?? null, status: "proposed", proposalJson: JSON.stringify(proposal) });
        const created = await db.select().from(aiPlans).where(and(eq(aiPlans.workspaceId, workspace.id), eq(aiPlans.intent, input.intent))).orderBy(desc(aiPlans.createdAt)).limit(1);
        await db.insert(notifications).values({ workspaceId: workspace.id, channel: "in_app", deliveryStatus: "delivered", title: "AI plan ready for review", body: "Your proposal is waiting for explicit approval.", type: "ai_approval" });
        return { plan: created[0], proposal };
      }),
    approve: protectedProcedure
      .input(z.object({ aiPlanId: z.number().int().positive(), idempotencyKey: z.string().min(8).max(120) }))
      .mutation(async ({ ctx, input }) => {
        const workspace = await ensureWorkspace(ctx.user.id);
        const db = await dbOrThrow();
        const plan = await db.select().from(aiPlans).where(and(eq(aiPlans.id, input.aiPlanId), eq(aiPlans.workspaceId, workspace.id))).limit(1);
        if (!plan[0]) throw new TRPCError({ code: "NOT_FOUND", message: "AI plan not found in this workspace" });
        const applicationState = resolvePlanApplicationState(plan[0]);
        if (applicationState === "idempotent") return { applied: false, idempotent: true };
        if (applicationState !== "ready") {
          throw new TRPCError({ code: "BAD_REQUEST", message: "Only proposed AI plans can be approved" });
        }
        const proposal = proposalSchema.parse(JSON.parse(plan[0].proposalJson));
        const defaultCalendar = await ensureDefaultCalendar(workspace.id);
        let activeGoalId = plan[0].contextGoalId;
        let activeTaskId = plan[0].contextTaskId;

        for (const item of proposal.commands) {
          if (item.command === "CreateGoal" && plan[0].contextDreamId) {
            await db.insert(goals).values({ workspaceId: workspace.id, dreamId: plan[0].contextDreamId, title: item.title, description: item.description, status: "active", targetDate: null });
            const goal = await db.select().from(goals).where(and(eq(goals.workspaceId, workspace.id), eq(goals.title, item.title))).orderBy(desc(goals.createdAt)).limit(1);
            activeGoalId = goal[0]?.id ?? activeGoalId;
          }
          if (item.command === "CreateRoadmap" && activeGoalId) {
            await db.insert(roadmaps).values({ workspaceId: workspace.id, goalId: activeGoalId, title: item.title, status: "active" });
          }
          if (item.command === "CreateTask") {
            await db.insert(tasks).values({ workspaceId: workspace.id, actionId: null, milestoneId: null, parentId: null, title: item.title, priority: "medium", status: "todo", estimateMinutes: item.estimateMinutes ?? 30, dueAt: null });
            const task = await db.select().from(tasks).where(and(eq(tasks.workspaceId, workspace.id), eq(tasks.title, item.title))).orderBy(desc(tasks.createdAt)).limit(1);
            activeTaskId = task[0]?.id ?? activeTaskId;
          }
          if (item.command === "ProjectTaskToCalendar" && activeTaskId) {
            const startsAt = new Date(Date.now() + (item.dayOffset ?? 1) * 86400000);
            startsAt.setHours(9, 0, 0, 0);
            const endsAt = new Date(startsAt.getTime() + (item.estimateMinutes ?? 30) * 60000);
            await db.insert(calendarEvents).values({ workspaceId: workspace.id, calendarId: defaultCalendar.id, taskId: activeTaskId, actionId: null, title: item.title, startsAt, endsAt, status: "scheduled" });
          }
          if (item.command === "SuggestCalendarSlots") {
            await db.insert(notifications).values({ workspaceId: workspace.id, channel: "in_app", deliveryStatus: "delivered", title: item.title, body: item.description, type: "calendar_suggestion" });
          }
        }
        await db.update(aiPlans).set({ status: "applied", appliedAt: new Date(), idempotencyKey: input.idempotencyKey }).where(eq(aiPlans.id, plan[0].id));
        return { applied: true, idempotent: false };
      }),
  }),

  notifications: router({
    markRead: protectedProcedure
      .input(z.object({ notificationId: z.number().int().positive() }))
      .mutation(async ({ ctx, input }) => {
        const workspace = await ensureWorkspace(ctx.user.id);
        await requireOwnedRecord(notifications, input.notificationId, workspace.id, "Notification");
        const db = await dbOrThrow();
        await db.update(notifications).set({ readAt: new Date() }).where(eq(notifications.id, input.notificationId));
        return { success: true };
      }),
  }),
});
