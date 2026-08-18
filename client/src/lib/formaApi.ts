import { useMutation, useQuery } from "@tanstack/react-query";

type MutationOptions<TOutput> = {
  onSuccess?: (data: TOutput) => void;
};

type EntityId = string | number;

export type DashboardData = {
  workspace: { id: string; name: string };
  dreams: any[];
  goals: any[];
  roadmaps: any[];
  milestones: any[];
  actions: any[];
  tasks: any[];
  calendars: any[];
  events: any[];
  timeEntries: any[];
  notifications: any[];
};

const API_BASE = import.meta.env.VITE_FORMA_API_URL ?? "/api/v1";

function getAccessToken() {
  return window.localStorage.getItem("forma_access_token");
}

function getWorkspaceId() {
  return window.localStorage.getItem("forma_workspace_id");
}

function getDevelopmentUserId() {
  const existing = window.localStorage.getItem("forma_development_user_id");
  if (existing) return existing;
  const generated = crypto.randomUUID();
  window.localStorage.setItem("forma_development_user_id", generated);
  return generated;
}

function idempotencyKey() {
  return crypto.randomUUID?.() ?? `forma-${Date.now()}-${Math.random()}`;
}

async function apiRequest<T>(path: string, init: RequestInit = {}): Promise<T> {
  const token = getAccessToken();
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(!token && import.meta.env.DEV ? { "X-User-Id": getDevelopmentUserId() } : {}),
      ...((init.method && init.method !== "GET") ? { "Idempotency-Key": idempotencyKey() } : {}),
      ...init.headers,
    },
  });
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new Error(body?.message ?? body?.detail?.message ?? "Forma API request failed");
  }
  return response.json() as Promise<T>;
}

function workspacePayload<T extends object>(payload: T) {
  const workspaceId = getWorkspaceId();
  if (!workspaceId) throw new Error("A Forma workspace must be selected before creating data.");
  return { ...payload, workspace_id: workspaceId };
}

function useFormaMutation<TInput extends object, TOutput>(
  handler: (input: TInput) => Promise<TOutput>,
  options?: MutationOptions<TOutput>,
) {
  return useMutation({ mutationFn: handler, onSuccess: options?.onSuccess });
}

export const formaApi = {
  workspaces: {
    create: {
      useMutation: (options?: MutationOptions<{ id: string; name: string }>) =>
        useFormaMutation(
          (input: { name: string }) =>
            apiRequest<{ id: string; name: string }>("/workspaces", {
              method: "POST",
              body: JSON.stringify({ name: input.name }),
            }),
          options,
        ),
    },
  },
  overview: {
    useQuery: () => {
      const workspaceId = getWorkspaceId();
      return useQuery({
        queryKey: ["forma", "dashboard", workspaceId],
        enabled: Boolean(workspaceId),
        queryFn: () =>
          apiRequest<DashboardData>(`/bff/workspaces/${workspaceId}/dashboard`).then(data => ({
            ...data,
            timeEntries: data.timeEntries ?? (data as any).time_entries ?? [],
          })),
      });
    },
  },
  dreams: {
    create: {
      useMutation: (options?: MutationOptions<unknown>) =>
        useFormaMutation(
          (input: { title: string; description?: string; color?: string }) =>
            apiRequest("/dreams", {
              method: "POST",
              body: JSON.stringify(workspacePayload({ title: input.title, description: input.description, visual_config: { color: input.color } })),
            }),
          options,
        ),
    },
  },
  goals: {
    create: {
      useMutation: (options?: MutationOptions<unknown>) =>
        useFormaMutation(
          (input: { dreamId: EntityId; title: string }) =>
            apiRequest("/goals", { method: "POST", body: JSON.stringify(workspacePayload({ dream_id: String(input.dreamId), title: input.title })) }),
          options,
        ),
    },
  },
  roadmaps: {
    create: {
      useMutation: (options?: MutationOptions<unknown>) =>
        useFormaMutation(
          (input: { goalId: EntityId; title: string }) =>
            apiRequest("/roadmaps", { method: "POST", body: JSON.stringify(workspacePayload({ goal_id: String(input.goalId), title: input.title })) }),
          options,
        ),
    },
  },
  milestones: {
    create: {
      useMutation: (options?: MutationOptions<unknown>) =>
        useFormaMutation(
          (input: { roadmapId: EntityId; title: string }) =>
            apiRequest("/milestones", { method: "POST", body: JSON.stringify(workspacePayload({ roadmap_id: String(input.roadmapId), title: input.title })) }),
          options,
        ),
    },
  },
  actions: {
    create: {
      useMutation: (options?: MutationOptions<unknown>) =>
        useFormaMutation(
          (input: { goalId?: EntityId; milestoneId?: EntityId; title: string; estimateMinutes?: number }) =>
            apiRequest("/actions", { method: "POST", body: JSON.stringify(workspacePayload({ goal_id: input.goalId === undefined ? undefined : String(input.goalId), milestone_id: input.milestoneId === undefined ? undefined : String(input.milestoneId), title: input.title, estimate_minutes: input.estimateMinutes })) }),
          options,
        ),
    },
  },
  tasks: {
    create: {
      useMutation: (options?: MutationOptions<unknown>) =>
        useFormaMutation(
          (input: { title: string; estimateMinutes?: number; priority?: string; dueAt?: Date; parentId?: EntityId; actionId?: EntityId; milestoneId?: EntityId }) =>
            apiRequest("/tasks", { method: "POST", body: JSON.stringify(workspacePayload({ title: input.title, estimate_minutes: input.estimateMinutes, priority: input.priority, due_at: input.dueAt, parent_id: input.parentId === undefined ? undefined : String(input.parentId), action_id: input.actionId === undefined ? undefined : String(input.actionId), milestone_id: input.milestoneId === undefined ? undefined : String(input.milestoneId) })) }),
          options,
        ),
    },
    updateStatus: {
      useMutation: (options?: MutationOptions<unknown>) =>
        useFormaMutation(
          (input: { taskId: EntityId; status: string }) =>
            apiRequest(`/tasks/${String(input.taskId)}/status`, { method: "PATCH", body: JSON.stringify(workspacePayload({ status: input.status })) }),
          options,
        ),
    },
  },
  calendars: {
    create: {
      useMutation: (options?: MutationOptions<unknown>) =>
        useFormaMutation(
          (input: { name: string; calendarType: string; color?: string }) =>
            apiRequest("/calendars", { method: "POST", body: JSON.stringify(workspacePayload({ name: input.name, calendar_type: input.calendarType, color: input.color })) }),
          options,
        ),
    },
    schedule: {
      useMutation: (options?: MutationOptions<unknown>) =>
        useFormaMutation(
          (input: { title: string; taskId?: EntityId; calendarId?: EntityId; startsAt: Date; endsAt: Date }) => {
            if (input.calendarId === undefined) throw new Error("Choose a calendar before scheduling a block.");
            return apiRequest("/calendar-events", { method: "POST", body: JSON.stringify(workspacePayload({ title: input.title, task_id: input.taskId === undefined ? undefined : String(input.taskId), calendar_id: String(input.calendarId), starts_at: input.startsAt, ends_at: input.endsAt })) });
          },
          options,
        ),
    },
    reschedule: {
      useMutation: (options?: MutationOptions<unknown>) =>
        useFormaMutation(
          (input: { eventId: EntityId; startsAt: Date; endsAt: Date }) =>
            apiRequest(`/calendar-events/${String(input.eventId)}`, { method: "PATCH", body: JSON.stringify(workspacePayload({ starts_at: input.startsAt, ends_at: input.endsAt })) }),
          options,
        ),
    },
  },
  time: {
    addManual: {
      useMutation: (options?: MutationOptions<unknown>) =>
        useFormaMutation(
          (input: { taskId: EntityId; startedAt: Date; endedAt: Date }) =>
            apiRequest("/time-entries", { method: "POST", body: JSON.stringify(workspacePayload({ task_id: String(input.taskId), started_at: input.startedAt, ended_at: input.endedAt })) }),
          options,
        ),
    },
    start: {
      useMutation: (options?: MutationOptions<unknown>) =>
        useFormaMutation(
          (input: { taskId: EntityId }) => apiRequest("/time-entries/timer/start", { method: "POST", body: JSON.stringify(workspacePayload({ task_id: String(input.taskId) })) }),
          options,
        ),
    },
    stop: {
      useMutation: (options?: MutationOptions<unknown>) =>
        useFormaMutation(
          (input: { taskId: EntityId }) => apiRequest("/time-entries/timer/stop", { method: "POST", body: JSON.stringify(workspacePayload({ task_id: String(input.taskId) })) }),
          options,
        ),
    },
  },
  ai: {
    propose: {
      useMutation: (options?: MutationOptions<any>) =>
        useFormaMutation(
          (input: { intent: string }) =>
            apiRequest<any>("/ai/plans", {
              method: "POST",
              body: JSON.stringify(
                workspacePayload({
                  prompt: input.intent,
                  commands: [{ command: "SuggestCalendarSlots", arguments: { intent: input.intent } }],
                }),
              ),
            }).then(plan => ({
              plan: { id: plan.id },
              proposal: {
                summary: "Forma prepared a calendar-slot suggestion. Review it before applying any change.",
                commands: [{ command: "SuggestCalendarSlots", title: "Review suggested focus slots", description: input.intent }],
              },
            })),
          options,
        ),
    },
    approve: {
      useMutation: (options?: MutationOptions<unknown>) =>
        useFormaMutation(
          (input: { aiPlanId: string; idempotencyKey?: string }) => {
            const workspaceId = getWorkspaceId();
            if (!workspaceId) throw new Error("A Forma workspace must be selected before approving a plan.");
            return apiRequest(`/ai/plans/${input.aiPlanId}/approve?workspace_id=${workspaceId}`, {
              method: "POST",
              headers: input.idempotencyKey ? { "Idempotency-Key": input.idempotencyKey } : undefined,
            });
          },
          options,
        ),
    },
  },
};
