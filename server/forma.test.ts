import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("./db", () => ({ getDb: vi.fn() }));

import { getDb } from "./db";
import { formaRouter, isWorkspaceScoped, resolveEmailDeliveryMode, resolvePlanApplicationState, validateAIProposal } from "./forma";

const getDbMock = vi.mocked(getDb);

function createFakeDb(selections: Array<Array<Record<string, unknown>>>) {
  const values = vi.fn().mockResolvedValue(undefined);
  const query = () => ({
    from: () => ({
      where: () => ({
        limit: async () => selections.shift() ?? [],
      }),
    }),
  });

  return {
    select: vi.fn(query),
    insert: vi.fn(() => ({ values })),
    update: vi.fn(() => ({ set: () => ({ where: vi.fn().mockResolvedValue(undefined) }) })),
    insertedValues: values,
  };
}

function caller() {
  return formaRouter.createCaller({
    user: { id: 7, openId: "forma-test-user" },
    req: { headers: {} },
    res: {},
  } as any);
}

describe("Forma AI plan guardrails", () => {
  it("accepts only the fixed AI command set", () => {
    const valid = validateAIProposal({
      summary: "A focused proposal",
      commands: [{ command: "CreateTask", title: "Choose one next step", description: "A small action for today.", estimateMinutes: 45, dayOffset: 0 }],
    });
    const invalid = validateAIProposal({
      summary: "Unsafe proposal",
      commands: [{ command: "DeleteCalendar", title: "Remove all events", description: "" }],
    });

    expect(valid.success).toBe(true);
    expect(invalid.success).toBe(false);
  });

  it("requires a proposed plan and prevents duplicate application", () => {
    expect(resolvePlanApplicationState({ status: "proposed", appliedAt: null })).toBe("ready");
    expect(resolvePlanApplicationState({ status: "applied", appliedAt: new Date() })).toBe("idempotent");
    expect(resolvePlanApplicationState({ status: "rejected", appliedAt: null })).toBe("not_approvable");
  });
});

describe("Forma notification delivery configuration", () => {
  it("keeps email notifications queued without a provider and enables delivery only with a supplied key", () => {
    expect(resolveEmailDeliveryMode("")).toBe("queued_without_provider");
    expect(resolveEmailDeliveryMode("resend_test_key")).toBe("external_delivery_ready");
  });
});

describe("Forma workspace tenancy", () => {
  beforeEach(() => vi.clearAllMocks());

  it("allows records only inside their own workspace boundary", () => {
    expect(isWorkspaceScoped({ workspaceId: 41 }, 41)).toBe(true);
    expect(isWorkspaceScoped({ workspaceId: 41 }, 42)).toBe(false);
  });

  it("rejects a goal mutation when the selected dream is outside the workspace", async () => {
    const db = createFakeDb([
      [{ id: 1, ownerId: 7, name: "Mine", timezone: "UTC" }],
      [],
    ]);
    getDbMock.mockResolvedValue(db as any);

    await expect(caller().goals.create({ dreamId: 999, title: "Another workspace dream" })).rejects.toMatchObject({ code: "NOT_FOUND" });
    expect(db.insertedValues).not.toHaveBeenCalled();
  });

  it("rejects cross-workspace status updates and scheduling references", async () => {
    const updateDb = createFakeDb([
      [{ id: 1, ownerId: 7, name: "Mine", timezone: "UTC" }],
      [],
    ]);
    getDbMock.mockResolvedValue(updateDb as any);
    await expect(caller().tasks.updateStatus({ taskId: 888, status: "done" })).rejects.toMatchObject({ code: "NOT_FOUND" });

    const scheduleDb = createFakeDb([
      [{ id: 1, ownerId: 7, name: "Mine", timezone: "UTC" }],
      [{ id: 70, workspaceId: 1 }],
      [],
    ]);
    getDbMock.mockResolvedValue(scheduleDb as any);
    await expect(caller().calendars.schedule({ calendarId: 70, taskId: 999, title: "Foreign task", startsAt: new Date("2026-08-20T09:00:00Z"), endsAt: new Date("2026-08-20T10:00:00Z") })).rejects.toMatchObject({ code: "NOT_FOUND" });
    expect(scheduleDb.insertedValues).not.toHaveBeenCalled();

    const taskDb = createFakeDb([
      [{ id: 1, ownerId: 7, name: "Mine", timezone: "UTC" }],
      [],
    ]);
    getDbMock.mockResolvedValue(taskDb as any);
    await expect(caller().tasks.create({ actionId: 404, title: "Foreign action", priority: "medium", estimateMinutes: 30 })).rejects.toMatchObject({ code: "NOT_FOUND" });
    expect(taskDb.insertedValues).not.toHaveBeenCalled();

    const milestoneDb = createFakeDb([
      [{ id: 1, ownerId: 7, name: "Mine", timezone: "UTC" }],
      [],
    ]);
    getDbMock.mockResolvedValue(milestoneDb as any);
    await expect(caller().tasks.create({ milestoneId: 405, title: "Foreign milestone", priority: "medium", estimateMinutes: 30 })).rejects.toMatchObject({ code: "NOT_FOUND" });
    expect(milestoneDb.insertedValues).not.toHaveBeenCalled();

    const timeDb = createFakeDb([
      [{ id: 1, ownerId: 7, name: "Mine", timezone: "UTC" }],
      [],
    ]);
    getDbMock.mockResolvedValue(timeDb as any);
    await expect(caller().time.addManual({ taskId: 404, startedAt: new Date("2026-08-20T09:00:00Z"), endedAt: new Date("2026-08-20T10:00:00Z") })).rejects.toMatchObject({ code: "NOT_FOUND" });
    expect(timeDb.insertedValues).not.toHaveBeenCalled();
  });
});

describe("Forma domain chain", () => {
  beforeEach(() => vi.clearAllMocks());

  it("persists the linked journey from dream to goal, roadmap, milestone, action, task, calendar and time entry", async () => {
    const db = createFakeDb([
      [{ id: 1, ownerId: 7, name: "Forma space", timezone: "UTC" }],
      [{ id: 1, ownerId: 7, name: "Forma space", timezone: "UTC" }],
      [{ id: 11, workspaceId: 1 }],
      [{ id: 1, ownerId: 7, name: "Forma space", timezone: "UTC" }],
      [{ id: 21, workspaceId: 1 }],
      [{ id: 1, ownerId: 7, name: "Forma space", timezone: "UTC" }],
      [{ id: 31, workspaceId: 1 }],
      [{ id: 1, ownerId: 7, name: "Forma space", timezone: "UTC" }],
      [{ id: 41, workspaceId: 1 }],
      [{ id: 1, ownerId: 7, name: "Forma space", timezone: "UTC" }],
      [{ id: 51, workspaceId: 1 }],
      [{ id: 41, workspaceId: 1 }],
      [{ id: 1, ownerId: 7, name: "Forma space", timezone: "UTC" }],
      [{ id: 61, workspaceId: 1 }],
      [{ id: 71, workspaceId: 1 }],
      [{ id: 1, ownerId: 7, name: "Forma space", timezone: "UTC" }],
      [{ id: 71, workspaceId: 1 }],
    ]);
    getDbMock.mockResolvedValue(db as any);
    const api = caller();
    const startsAt = new Date("2026-08-20T09:00:00Z");
    const endsAt = new Date("2026-08-20T10:00:00Z");

    await api.dreams.create({ title: "A sustainable creative life", description: "Make room for deliberate practice.", color: "#7163f6" });
    await api.goals.create({ dreamId: 11, title: "Run a sustainable creative practice" });
    await api.roadmaps.create({ goalId: 21, title: "Build the foundation" });
    await api.milestones.create({ roadmapId: 31, title: "Establish weekly cadence" });
    await api.actions.create({ milestoneId: 41, title: "Outline the first three sessions", estimateMinutes: 45 });
    await api.tasks.create({ actionId: 51, milestoneId: 41, title: "Block first session", priority: "high", estimateMinutes: 60 });
    await api.calendars.schedule({ calendarId: 61, taskId: 71, title: "First creative session", startsAt, endsAt });
    await api.time.addManual({ taskId: 71, startedAt: startsAt, endedAt: endsAt });

    const inserted = db.insertedValues.mock.calls.map(([value]) => value);
    expect(inserted).toEqual(expect.arrayContaining([
      expect.objectContaining({ workspaceId: 1, title: "A sustainable creative life", status: "active" }),
      expect.objectContaining({ workspaceId: 1, dreamId: 11, title: "Run a sustainable creative practice" }),
      expect.objectContaining({ workspaceId: 1, goalId: 21, title: "Build the foundation" }),
      expect.objectContaining({ workspaceId: 1, roadmapId: 31, title: "Establish weekly cadence" }),
      expect.objectContaining({ workspaceId: 1, milestoneId: 41, title: "Outline the first three sessions" }),
      expect.objectContaining({ workspaceId: 1, actionId: 51, milestoneId: 41, title: "Block first session" }),
      expect.objectContaining({ workspaceId: 1, calendarId: 61, taskId: 71, title: "First creative session" }),
      expect.objectContaining({ workspaceId: 1, taskId: 71, durationSeconds: 3600, source: "manual" }),
    ]));
  });
});
