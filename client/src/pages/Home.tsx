import { useAuth } from "@/_core/hooks/useAuth";
import DashboardLayout from "@/components/DashboardLayout";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Progress } from "@/components/ui/progress";
import { Textarea } from "@/components/ui/textarea";
import { startLogin } from "@/const";
import { calendarBackLevel, calendarBreadcrumb, calendarLevelLabel, moveCalendarCursor, type CalendarLevel } from "@/lib/calendarNavigation";
import { formaApi } from "@/lib/formaApi";
import { cn } from "@/lib/utils";
import {
  ArrowLeft,
  ArrowRight,
  Bell,
  CalendarDays,
  Check,
  CheckCircle2,
  ChevronLeft,
  ChevronRight,
  Circle,
  Clock3,
  Compass,
  Diamond,
  Flame,
  Goal,
  GripVertical,
  Layers3,
  Lightbulb,
  ListChecks,
  Map as MapIcon,
  MoreHorizontal,
  MoveRight,
  Pause,
  Play,
  Plus,
  Sparkles,
  Target,
  TimerReset,
  WandSparkles,
} from "lucide-react";
import React, { useMemo, useState, type DragEvent, type FormEvent } from "react";
import { useLocation } from "wouter";

type ViewName = "today" | "dreams" | "calendar" | "flow" | "assistant";
type PlanCommand = {
  command: "CreateGoal" | "CreateRoadmap" | "CreateTask" | "SuggestCalendarSlots" | "ProjectTaskToCalendar";
  title: string;
  description: string;
  estimateMinutes?: number;
  dayOffset?: number;
};

const viewCopy: Record<ViewName, { eyebrow: string; title: string; description: string }> = {
  today: { eyebrow: "Ваш живой план", title: "Направьте сегодняшний день.", description: "Каждый фокус-блок связан с чем-то большим." },
  dreams: { eyebrow: "Ваши ориентиры", title: "Придайте будущему форму.", description: "Мечты задают эмоциональное направление вашим планам." },
  calendar: { eyebrow: "Время на виду", title: "Берегите время для важного.", description: "Переходите от месяца к работе, которая движет вас вперёд." },
  flow: { eyebrow: "Ваш план в движении", title: "Видьте связи.", description: "Наблюдайте путь между намерениями, целями и следующими действиями." },
  assistant: { eyebrow: "Интеллект Forma", title: "Попросите более ясный путь.", description: "Проверяйте каждое предложенное изменение до применения Forma." },
};

const commandTone: Record<PlanCommand["command"], string> = {
  CreateGoal: "bg-violet-100 text-violet-700",
  CreateRoadmap: "bg-blue-100 text-blue-700",
  CreateTask: "bg-orange-100 text-orange-700",
  SuggestCalendarSlots: "bg-emerald-100 text-emerald-700",
  ProjectTaskToCalendar: "bg-rose-100 text-rose-700",
};

const commandLabel: Record<PlanCommand["command"], string> = {
  CreateGoal: "Создать цель",
  CreateRoadmap: "Создать дорожную карту",
  CreateTask: "Создать задачу",
  SuggestCalendarSlots: "Предложить слоты в календаре",
  ProjectTaskToCalendar: "Запланировать задачу в календаре",
};

const priorityCopy: Record<string, string> = {
  low: "низкий",
  medium: "средний",
  high: "высокий",
  critical: "критический",
};

const statusCopy: Record<string, string> = {
  active: "активна",
  done: "выполнено",
  todo: "к выполнению",
  planned: "запланировано",
  completed: "завершено",
  archived: "в архиве",
};

const notificationCopy: Record<string, { title: string; body: string }> = {
  AIPlanProposed: { title: "Предложение AI готово", body: "Просмотрите предложенные изменения перед применением." },
  AIPlanApproved: { title: "Предложение AI применено", body: "Подтверждённые вами изменения добавлены в пространство." },
  TaskCreated: { title: "Задача добавлена", body: "Назначьте срок, приоритет или блок времени в календаре." },
  TaskStatusUpdated: { title: "Статус задачи изменён", body: "Проверьте следующий шаг в списке задач." },
  TaskDueSoon: { title: "Срок задачи приближается", body: "Уточните следующий шаг или перенесите время в календаре." },
  TaskReminder: { title: "Напоминание о задаче", body: "Вернитесь к запланированной работе, когда будете готовы." },
  CalendarEventScheduled: { title: "Блок времени запланирован", body: "Откройте календарь, чтобы сверить время и приоритет." },
  CalendarEventRescheduled: { title: "Календарный блок перенесён", body: "Проверьте обновлённое время в календаре." },
  CalendarEventReminder: { title: "Напоминание о календарном блоке", body: "Скоро начнётся запланированный блок времени." },
};

function localizedStatus(value: string) {
  return statusCopy[value] ?? value;
}

function localizedNotification(notification: { title: string; body: string }) {
  return notificationCopy[notification.title] ?? notificationCopy[notification.body] ?? notification;
}

function friendlyDate(date: Date | string | null | undefined, options: Intl.DateTimeFormatOptions = { month: "short", day: "numeric" }) {
  if (!date) return "Без даты";
  return new Intl.DateTimeFormat("ru-RU", options).format(new Date(date));
}

function minutes(value: number) {
  if (!value) return "0 мин";
  const hours = Math.floor(value / 60);
  return hours ? `${hours} ч ${value % 60 ? `${value % 60} мин` : ""}`.trim() : `${value} мин`;
}

function seconds(value: number) {
  const h = Math.floor(value / 3600);
  const m = Math.floor((value % 3600) / 60);
  const s = value % 60;
  return `${h ? `${String(h).padStart(2, "0")}:` : ""}${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
}

function startOfWeek(date: Date) {
  const next = new Date(date);
  const weekday = (next.getDay() + 6) % 7;
  next.setDate(next.getDate() - weekday);
  next.setHours(0, 0, 0, 0);
  return next;
}

function dateKey(date: Date | string) {
  const value = new Date(date);
  return `${value.getFullYear()}-${String(value.getMonth() + 1).padStart(2, "0")}-${String(value.getDate()).padStart(2, "0")}`;
}

function colorFromVisual(config: string) {
  try {
    return JSON.parse(config).color ?? "#7266f0";
  } catch {
    return "#7266f0";
  }
}

function randomKey() {
  return typeof crypto !== "undefined" && crypto.randomUUID ? crypto.randomUUID() : `forma-${Date.now()}-${Math.random()}`;
}

function Landing() {
  return (
    <div className="landing-shell min-h-screen overflow-hidden px-5 py-6 sm:px-10">
      <nav className="mx-auto flex max-w-7xl items-center justify-between py-3">
        <Brand />
        <Button onClick={() => startLogin()} className="rounded-full bg-[#1b1a2b] px-5 text-white shadow-none hover:bg-[#2c2a46]">Открыть Forma <ArrowRight className="ml-2 h-4 w-4" /></Button>
      </nav>
      <main className="mx-auto grid max-w-7xl gap-14 pt-20 lg:grid-cols-[1.05fr_.95fr] lg:items-center lg:pt-28">
        <section className="max-w-2xl">
          <p className="eyebrow"><span /> Твоё будущее начинается сегодня</p>
          <h1 className="mt-6 font-display text-5xl font-medium leading-[.98] tracking-[-.055em] text-[#1b1a2b] sm:text-7xl">Стань его <em>творцом.</em></h1>
          <p className="mt-7 max-w-xl text-lg leading-8 text-[#696577]">Forma превращает мечты в видимые цели, защищённое время и сфокусированную работу, из которой рождается прогресс.</p>
          <div className="mt-10 flex flex-wrap gap-3"><Button onClick={() => startLogin()} size="lg" className="rounded-full bg-[#7163f6] px-7 shadow-[0_14px_34px_rgba(113,99,246,.26)] hover:bg-[#6053e9]">Создать пространство <MoveRight className="ml-2 h-4 w-4" /></Button><Button variant="outline" size="lg" className="rounded-full border-[#dcd7f1] bg-white/60 px-7 text-[#3c3851]">Как это работает</Button></div>
          <div className="mt-14 flex items-center gap-7 text-sm text-[#777284]"><span className="flex items-center gap-2"><CheckCircle2 className="h-4 w-4 text-[#7266f0]" /> От мечты к действию</span><span className="flex items-center gap-2"><CheckCircle2 className="h-4 w-4 text-[#7266f0]" /> Ваш темп, ваша система</span></div>
        </section>
        <section className="relative min-h-[490px]">
          <div className="absolute inset-x-4 top-4 h-[430px] rounded-[38px] bg-[#ffffffba] shadow-[0_26px_90px_rgba(61,53,107,.15)] backdrop-blur" />
          <div className="relative z-10 mx-auto mt-8 max-w-[460px] rounded-[32px] border border-white/70 bg-[#fbfaff] p-6 shadow-[0_20px_60px_rgba(67,56,125,.12)]">
            <div className="flex items-center justify-between"><span className="text-sm font-medium text-[#7163f6]">FORMA / СЕГОДНЯ</span><span className="rounded-full bg-[#f1efff] px-3 py-1 text-xs text-[#6559df]">Воскресенье, 17</span></div>
            <p className="mt-8 font-display text-3xl tracking-[-.04em] text-[#242137]">Будущее, в котором больше места для жизни.</p>
            <div className="relative mt-10 h-48 overflow-hidden rounded-3xl bg-[#26223f] p-5 text-white"><div className="absolute -right-12 -top-12 h-40 w-40 rounded-full bg-[#ffbf7e] opacity-90" /><div className="absolute -bottom-14 left-12 h-36 w-36 rounded-full bg-[#8c7fff]" /><span className="relative text-xs uppercase tracking-[.16em] text-white/55">МЕЧТА</span><p className="relative mt-3 max-w-[220px] text-xl font-medium leading-6">Создать жизнь, отражающую то, что для вас важно.</p><div className="absolute bottom-5 left-5 flex items-center gap-2 text-xs text-white/65"><Diamond className="h-3.5 w-3.5" /> Личное видение</div></div>
            <div className="mt-5 flex items-center justify-between rounded-2xl bg-[#f2f0ff] p-4"><div className="flex items-center gap-3"><div className="grid h-9 w-9 place-items-center rounded-xl bg-[#7567f5] text-white"><Target className="h-4 w-4" /></div><div><p className="text-sm font-medium text-[#302b49]">Следующий значимый шаг</p><p className="text-xs text-[#77718f]">45 минут защищённого времени сегодня</p></div></div><Play className="h-4 w-4 text-[#7567f5]" /></div>
          </div>
        </section>
      </main>
    </div>
  );
}

function Brand() {
  return <div className="flex items-center gap-3"><div className="grid h-9 w-9 place-items-center rounded-[14px] bg-[#1f1d33] text-white shadow-[0_8px_20px_rgba(42,37,76,.2)]"><Diamond className="h-[17px] w-[17px] fill-[#c4bdff] text-[#c4bdff]" /></div><span className="font-display text-2xl font-semibold tracking-[-.07em] text-[#201d34]">forma</span></div>;
}

function Stat({ icon: Icon, label, value, detail, accent }: { icon: typeof Target; label: string; value: string; detail: string; accent: string }) {
  return <div className="surface-card group p-4"><div className="flex items-start justify-between"><span className={cn("grid h-9 w-9 place-items-center rounded-xl", accent)}><Icon className="h-4 w-4" /></span><MoreHorizontal className="h-4 w-4 text-[#a7a2b5] opacity-0 transition-opacity group-hover:opacity-100" /></div><p className="mt-5 text-xs font-medium uppercase tracking-[.12em] text-[#908ba0]">{label}</p><p className="mt-1 font-display text-3xl tracking-[-.05em] text-[#29253c]">{value}</p><p className="mt-1.5 text-xs text-[#817c8e]">{detail}</p></div>;
}

function WorkspaceHeader({ view, workspaceName, unread }: { view: ViewName; workspaceName: string; unread: number }) {
  const copy = viewCopy[view];
  return <header className="flex flex-col justify-between gap-5 border-b border-[#e9e6ef] pb-7 md:flex-row md:items-end"><div><p className="eyebrow"><span /> {copy.eyebrow}</p><h1 className="mt-3 font-display text-4xl tracking-[-.055em] text-[#27233b]">{copy.title}</h1><p className="mt-2 max-w-2xl text-sm leading-6 text-[#807b8d]">{copy.description}</p></div><div className="flex items-center gap-3"><div className="hidden rounded-full border border-[#e7e4ed] bg-white px-3 py-2 text-xs text-[#696376] sm:flex sm:items-center sm:gap-2"><Compass className="h-3.5 w-3.5 text-[#7163f6]" /> {workspaceName}</div><button className="relative grid h-10 w-10 place-items-center rounded-full border border-[#e7e4ed] bg-white text-[#555062] transition-transform hover:-translate-y-0.5" aria-label="Уведомления"><Bell className="h-4 w-4" />{unread > 0 && <span className="absolute right-0 top-0 grid h-4 min-w-4 place-items-center rounded-full bg-[#ff7464] px-1 text-[9px] font-bold text-white">{unread}</span>}</button></div></header>;
}

function CreateDream({ onCreated }: { onCreated: () => void }) {
  const [open, setOpen] = useState(false);
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const create = formaApi.dreams.create.useMutation({ onSuccess: () => { onCreated(); setOpen(false); setTitle(""); setDescription(""); } });
  const submit = (event: FormEvent) => { event.preventDefault(); create.mutate({ title, description, color: "#7163f6" }); };
  return <Dialog open={open} onOpenChange={setOpen}><DialogTrigger asChild><Button className="rounded-full bg-[#7163f6] px-5 hover:bg-[#6053e9]"><Plus className="mr-1.5 h-4 w-4" /> Новая мечта</Button></DialogTrigger><DialogContent className="rounded-3xl border-0 p-7 sm:max-w-md"><DialogHeader><DialogTitle className="font-display text-3xl tracking-[-.045em]">Дайте будущему имя.</DialogTitle><DialogDescription>Начните с образа жизни, перемены или опыта, которому хотите придать форму.</DialogDescription></DialogHeader><form onSubmit={submit} className="mt-4 space-y-4"><Input value={title} onChange={e => setTitle(e.target.value)} placeholder="Например: более спокойный и сильный год" className="rounded-xl border-[#e6e2ed]" required /><Textarea value={description} onChange={e => setDescription(e.target.value)} placeholder="Как это выглядит и ощущается?" className="min-h-28 rounded-xl border-[#e6e2ed]" /><Button disabled={create.isPending} className="w-full rounded-xl bg-[#7163f6] hover:bg-[#6053e9]">{create.isPending ? "Создаём…" : "Создать мечту"}</Button></form></DialogContent></Dialog>;
}

function CreateTask({ tasks, actions, milestones, onCreated }: { tasks: any[]; actions: any[]; milestones: any[]; onCreated: () => void }) {
  const [open, setOpen] = useState(false);
  const [title, setTitle] = useState("");
  const [estimate, setEstimate] = useState("45");
  const [priority, setPriority] = useState<"low" | "medium" | "high" | "critical">("medium");
  const [dueAt, setDueAt] = useState("");
  const [parentId, setParentId] = useState("");
  const [actionId, setActionId] = useState("");
  const [milestoneId, setMilestoneId] = useState("");
  const create = formaApi.tasks.create.useMutation({ onSuccess: () => { onCreated(); setOpen(false); setTitle(""); } });
  return <Dialog open={open} onOpenChange={setOpen}><DialogTrigger asChild><Button variant="outline" className="rounded-full border-[#ddd8e8] bg-white px-4 text-[#484258]"><Plus className="mr-1.5 h-4 w-4" /> Добавить задачу</Button></DialogTrigger><DialogContent className="max-h-[88vh] overflow-y-auto rounded-3xl border-0 p-7 sm:max-w-lg"><DialogHeader><DialogTitle className="font-display text-3xl tracking-[-.045em]">Назовите следующее действие.</DialogTitle><DialogDescription>Сделайте задачу конкретной, свяжите с контекстом и выделите для неё время.</DialogDescription></DialogHeader><form onSubmit={event => { event.preventDefault(); create.mutate({ title, estimateMinutes: Number(estimate), priority, dueAt: dueAt ? new Date(dueAt) : undefined, parentId: parentId || undefined, actionId: actionId || undefined, milestoneId: milestoneId || undefined }); }} className="mt-4 grid gap-3"><Input value={title} onChange={e => setTitle(e.target.value)} placeholder="Какой следующий значимый шаг?" required className="rounded-xl border-[#e6e2ed]" /><div className="grid gap-3 sm:grid-cols-2"><Input value={estimate} onChange={e => setEstimate(e.target.value)} type="number" min="15" max="1440" className="rounded-xl border-[#e6e2ed]" /><select value={priority} onChange={event => setPriority(event.target.value as typeof priority)} className="h-10 rounded-xl border border-[#e6e2ed] bg-white px-3 text-sm"><option value="low">Низкий приоритет</option><option value="medium">Средний приоритет</option><option value="high">Высокий приоритет</option><option value="critical">Критический приоритет</option></select></div><Input value={dueAt} onChange={event => setDueAt(event.target.value)} type="datetime-local" className="rounded-xl border-[#e6e2ed]" /><div className="grid gap-3 sm:grid-cols-2"><select value={actionId} onChange={event => setActionId(event.target.value)} className="h-10 rounded-xl border border-[#e6e2ed] bg-white px-3 text-sm"><option value="">Связать с действием (необязательно)</option>{actions.map(action => <option key={action.id} value={action.id}>{action.title}</option>)}</select><select value={milestoneId} onChange={event => setMilestoneId(event.target.value)} className="h-10 rounded-xl border border-[#e6e2ed] bg-white px-3 text-sm"><option value="">Связать с этапом (необязательно)</option>{milestones.map(milestone => <option key={milestone.id} value={milestone.id}>{milestone.title}</option>)}</select></div><select value={parentId} onChange={event => setParentId(event.target.value)} className="h-10 rounded-xl border border-[#e6e2ed] bg-white px-3 text-sm"><option value="">Самостоятельная задача</option>{tasks.map(task => <option key={task.id} value={task.id}>Подзадача для: {task.title}</option>)}</select><Button disabled={create.isPending} className="mt-1 w-full rounded-xl bg-[#1f1d33] hover:bg-[#312e4c]">{create.isPending ? "Сохраняем…" : "Сохранить задачу"}</Button></form></DialogContent></Dialog>;
}

function ScheduleBlock({ tasks, calendars, onScheduled }: { tasks: any[]; calendars: any[]; onScheduled: () => void }) {
  const [open, setOpen] = useState(false);
  const [title, setTitle] = useState("");
  const [taskId, setTaskId] = useState("");
  const [calendarId, setCalendarId] = useState("");
  const [startsAt, setStartsAt] = useState("");
  const [endsAt, setEndsAt] = useState("");
  const schedule = formaApi.calendars.schedule.useMutation({ onSuccess: () => { onScheduled(); setOpen(false); setTitle(""); } });
  const chooseTask = (value: string) => { setTaskId(value); const task = tasks.find(item => String(item.id) === value); if (task && !title) setTitle(task.title); };
  return <Dialog open={open} onOpenChange={setOpen}><DialogTrigger asChild><Button className="rounded-full bg-[#7163f6] px-4 hover:bg-[#6053e9]"><CalendarDays className="mr-1.5 h-4 w-4" /> Запланировать блок</Button></DialogTrigger><DialogContent className="rounded-3xl border-0 p-7 sm:max-w-lg"><DialogHeader><DialogTitle className="font-display text-3xl tracking-[-.045em]">Защитите это время.</DialogTitle><DialogDescription>Превратите задачу или действие в видимый блок в календаре.</DialogDescription></DialogHeader><form onSubmit={event => { event.preventDefault(); schedule.mutate({ title, taskId: taskId || undefined, calendarId: calendarId || undefined, startsAt: new Date(startsAt), endsAt: new Date(endsAt) }); }} className="mt-5 grid gap-3"><select value={taskId} onChange={event => chooseTask(event.target.value)} className="h-11 rounded-xl border border-[#e5e1eb] bg-white px-3 text-sm"><option value="">Независимый блок</option>{tasks.map(task => <option key={task.id} value={task.id}>{task.title}</option>)}</select><Input value={title} onChange={event => setTitle(event.target.value)} placeholder="Для чего вы хотите освободить это время?" required className="rounded-xl" /><select value={calendarId} onChange={event => setCalendarId(event.target.value)} className="h-11 rounded-xl border border-[#e5e1eb] bg-white px-3 text-sm"><option value="">Личный ритм (по умолчанию)</option>{calendars.map(calendar => <option key={calendar.id} value={calendar.id}>{calendar.name}</option>)}</select><div className="grid gap-3 sm:grid-cols-2"><Input value={startsAt} onChange={event => setStartsAt(event.target.value)} type="datetime-local" required className="rounded-xl" /><Input value={endsAt} onChange={event => setEndsAt(event.target.value)} type="datetime-local" required className="rounded-xl" /></div><Button disabled={schedule.isPending} className="mt-1 rounded-xl bg-[#1f1d33] hover:bg-[#312e4c]">{schedule.isPending ? "Планируем…" : "Запланировать блок"}</Button></form></DialogContent></Dialog>;
}

function CreateCalendar({ onCreated }: { onCreated: () => void }) {
  const [open, setOpen] = useState(false);
  const [name, setName] = useState("");
  const [calendarType, setCalendarType] = useState("personal");
  const [color, setColor] = useState("#7163f6");
  const create = formaApi.calendars.create.useMutation({ onSuccess: () => { onCreated(); setOpen(false); setName(""); } });
  return <Dialog open={open} onOpenChange={setOpen}><DialogTrigger asChild><Button variant="outline" className="rounded-full border-[#ded9e8] bg-white px-4 text-[#484258]"><Plus className="mr-1.5 h-4 w-4" /> Календарь</Button></DialogTrigger><DialogContent className="rounded-3xl border-0 p-7 sm:max-w-md"><DialogHeader><DialogTitle className="font-display text-3xl tracking-[-.045em]">Создайте календарь для жизни.</DialogTitle><DialogDescription>Разделите спорт, фокус, отношения и любой другой ритм, который хотите видеть.</DialogDescription></DialogHeader><form onSubmit={event => { event.preventDefault(); create.mutate({ name, calendarType, color }); }} className="mt-5 space-y-3"><Input value={name} onChange={event => setName(event.target.value)} placeholder="Например: глубокая работа" required className="rounded-xl" /><Input value={calendarType} onChange={event => setCalendarType(event.target.value)} placeholder="Тип, например: дисциплина" required className="rounded-xl" /><div className="flex items-center gap-3 rounded-xl border border-[#e5e1eb] px-3 py-2"><input value={color} onChange={event => setColor(event.target.value)} type="color" className="h-7 w-9 rounded border-0 bg-transparent p-0" /><span className="text-sm text-[#726c7b]">Выберите визуальный образ</span></div><Button disabled={create.isPending} className="w-full rounded-xl bg-[#7163f6]">{create.isPending ? "Создаём…" : "Создать календарь"}</Button></form></DialogContent></Dialog>;
}

function ManualTime({ tasks, onSaved }: { tasks: any[]; onSaved: () => void }) {
  const [open, setOpen] = useState(false);
  const [taskId, setTaskId] = useState("");
  const [startedAt, setStartedAt] = useState("");
  const [endedAt, setEndedAt] = useState("");
  const add = formaApi.time.addManual.useMutation({ onSuccess: () => { onSaved(); setOpen(false); } });
  return <Dialog open={open} onOpenChange={setOpen}><DialogTrigger asChild><Button size="sm" variant="ghost" className="rounded-full text-xs text-[#7568ee] hover:bg-[#f0eeff]"><TimerReset className="mr-1 h-3.5 w-3.5" /> Записать время</Button></DialogTrigger><DialogContent className="rounded-3xl border-0 p-7 sm:max-w-md"><DialogHeader><DialogTitle className="font-display text-3xl tracking-[-.045em]">Запишите реальную работу.</DialogTitle><DialogDescription>Учитывайте уже вложенное время, чтобы план оставался честным.</DialogDescription></DialogHeader><form onSubmit={event => { event.preventDefault(); add.mutate({ taskId, startedAt: new Date(startedAt), endedAt: new Date(endedAt) }); }} className="mt-5 space-y-3"><select value={taskId} onChange={event => setTaskId(event.target.value)} required className="h-11 w-full rounded-xl border border-[#e5e1eb] bg-white px-3 text-sm"><option value="">Выберите задачу</option>{tasks.map(task => <option key={task.id} value={task.id}>{task.title}</option>)}</select><Input type="datetime-local" value={startedAt} onChange={event => setStartedAt(event.target.value)} required className="rounded-xl" /><Input type="datetime-local" value={endedAt} onChange={event => setEndedAt(event.target.value)} required className="rounded-xl" /><Button disabled={add.isPending} className="w-full rounded-xl bg-[#1f1d33]">{add.isPending ? "Сохраняем…" : "Сохранить запись времени"}</Button></form></DialogContent></Dialog>;
}

function TaskList({ tasks, timeEntries, refresh }: { tasks: any[]; timeEntries: any[]; refresh: () => void }) {
  const update = formaApi.tasks.updateStatus.useMutation({ onSuccess: refresh });
  const start = formaApi.time.start.useMutation({ onSuccess: refresh });
  const stop = formaApi.time.stop.useMutation({ onSuccess: refresh });
  const runningTaskIds = new Set(timeEntries.filter(entry => !entry.endedAt).map(entry => entry.taskId));
  const tasksToShow = tasks.slice(0, 5);
  return <section className="surface-card overflow-hidden"><div className="flex items-center justify-between border-b border-[#efecf3] px-5 py-4"><div><p className="text-sm font-semibold text-[#343044]">Ваш список фокуса</p><p className="mt-0.5 text-xs text-[#8a8595]">Маленькие шаги, видимый импульс</p></div><div className="flex items-center gap-2"><ManualTime tasks={tasks} onSaved={refresh} /><ListChecks className="h-5 w-5 text-[#7163f6]" /></div></div><div className="divide-y divide-[#efecf3]">{tasksToShow.length ? tasksToShow.map(task => { const running = runningTaskIds.has(task.id); const actualMinutes = Math.round(timeEntries.filter(entry => entry.taskId === task.id).reduce((sum, entry) => sum + entry.durationSeconds, 0) / 60); const progress = task.estimateMinutes ? Math.min(100, Math.round((actualMinutes / task.estimateMinutes) * 100)) : 0; return <div key={task.id} className="group flex items-start gap-3 px-5 py-3.5"><button onClick={() => update.mutate({ taskId: task.id, status: task.status === "done" ? "todo" : "done" })} className={cn("mt-1 grid h-5 w-5 shrink-0 place-items-center rounded-full border transition-colors", task.status === "done" ? "border-[#7163f6] bg-[#7163f6] text-white" : "border-[#cfc9dc] text-transparent hover:border-[#7163f6]")}><Check className="h-3 w-3" /></button><div className="min-w-0 flex-1"><div className="flex items-center gap-2"><p className={cn("truncate text-sm font-medium", task.status === "done" ? "text-[#aaa5b1] line-through" : "text-[#3b374b]")}>{task.title}</p>{task.parentId && <span className="rounded-full bg-[#f0eeff] px-1.5 py-0.5 text-[9px] font-semibold text-[#6d61df]">подзадача</span>}</div><div className="mt-1 flex items-center gap-2 text-[11px] text-[#938e9d]"><span className={cn("priority-dot", `priority-${task.priority}`)} />{priorityCopy[task.priority] ?? task.priority} · {minutes(task.estimateMinutes)} {task.dueAt && `· ${friendlyDate(task.dueAt)}`}</div><div className="mt-2 flex items-center gap-2"><Progress value={progress} className="h-1.5 flex-1 bg-[#eeebf4] [&>div]:bg-[#7163f6]" /><span className="shrink-0 text-[10px] text-[#8e8898]">{minutes(actualMinutes)} / {minutes(task.estimateMinutes)}</span></div></div><Button onClick={() => running ? stop.mutate({ taskId: task.id }) : start.mutate({ taskId: task.id })} size="icon" variant="ghost" className={cn("mt-0.5 h-8 w-8 rounded-full", running ? "bg-[#fff0ed] text-[#ed735f]" : "text-[#8c8795] hover:bg-[#f0edff] hover:text-[#7163f6]")} aria-label={running ? "Остановить таймер" : "Запустить таймер"}>{running ? <Pause className="h-3.5 w-3.5 fill-current" /> : <Play className="h-3.5 w-3.5 fill-current" />}</Button></div>; }) : <div className="px-5 py-10 text-center"><Circle className="mx-auto h-7 w-7 text-[#d5d0dc]" /><p className="mt-3 text-sm font-medium text-[#615c6b]">День открыт.</p><p className="mt-1 text-xs text-[#9892a1]">Добавьте одну задачу, достойную вашего внимания.</p></div>}</div></section>;
}

function DreamCards({ dreams }: { dreams: any[] }) {
  return <section className="surface-card overflow-hidden"><div className="flex items-center justify-between border-b border-[#efecf3] px-5 py-4"><div><p className="text-sm font-semibold text-[#343044]">Мечты в фокусе</p><p className="mt-0.5 text-xs text-[#8a8595]">Направление за деталями</p></div><WandSparkles className="h-5 w-5 text-[#7163f6]" /></div><div className="grid gap-3 p-4">{dreams.length ? dreams.slice(0, 3).map((dream, index) => { const color = colorFromVisual(dream.visualConfig); return <article key={dream.id} className="dream-card" style={{ background: `linear-gradient(135deg, ${color}, #29243f 120%)` }}><div className="relative z-10"><div className="flex items-center justify-between"><span className="rounded-full bg-white/15 px-2.5 py-1 text-[10px] font-medium uppercase tracking-[.13em] text-white/80">{localizedStatus(dream.status)}</span><Diamond className="h-4 w-4 fill-white/30 text-white/80" /></div><h3 className="mt-9 font-display text-xl tracking-[-.035em] text-white">{dream.title}</h3><p className="mt-2 line-clamp-2 text-xs leading-5 text-white/70">{dream.description || "Направление, которому стоит дать место."}</p></div><div className="absolute -bottom-9 -right-8 h-28 w-28 rounded-full bg-white/20 blur-[1px]" />{index === 0 && <div className="absolute right-7 top-9 h-5 w-5 rounded-full border border-white/40 bg-white/15" />}</article>; }) : <div className="rounded-2xl bg-[#f7f5fb] p-7 text-center"><Lightbulb className="mx-auto h-7 w-7 text-[#9e94ee]" /><p className="mt-3 text-sm font-medium text-[#514b61]">Начните с мечты.</p><p className="mt-1 text-xs leading-5 text-[#928c9b]">Ваш визуальный ориентир сохранит смысл планов.</p></div>}</div></section>;
}

function GoalStudio({ dreams, goals, roadmaps, milestones, actions, refresh }: { dreams: any[]; goals: any[]; roadmaps: any[]; milestones: any[]; actions: any[]; refresh: () => void }) {
  const [goalTitle, setGoalTitle] = useState("");
  const [goalDreamId, setGoalDreamId] = useState("");
  const [roadmapTitle, setRoadmapTitle] = useState("");
  const [roadmapGoalId, setRoadmapGoalId] = useState("");
  const [milestoneTitle, setMilestoneTitle] = useState("");
  const [milestoneRoadmapId, setMilestoneRoadmapId] = useState("");
  const [actionTitle, setActionTitle] = useState("");
  const [actionMilestoneId, setActionMilestoneId] = useState("");
  const createGoal = formaApi.goals.create.useMutation({ onSuccess: refresh });
  const createRoadmap = formaApi.roadmaps.create.useMutation({ onSuccess: refresh });
  const createMilestone = formaApi.milestones.create.useMutation({ onSuccess: refresh });
  const createAction = formaApi.actions.create.useMutation({ onSuccess: refresh });
  const roadmapByGoal = (goalId: number) => roadmaps.filter(roadmap => roadmap.goalId === goalId);
  const milestonesByRoadmap = (roadmapId: number) => milestones.filter(milestone => milestone.roadmapId === roadmapId);
  const actionsByMilestone = (milestoneId: number) => actions.filter(action => action.milestoneId === milestoneId);
  return <section className="surface-card overflow-hidden"><div className="flex flex-col gap-4 border-b border-[#efecf3] p-5 sm:flex-row sm:items-center sm:justify-between"><div><p className="text-sm font-semibold text-[#343044]">Студия целей и дорожных карт</p><p className="mt-1 text-xs text-[#8a8595]">Мечта становится реальной, когда следующий этап понятен.</p></div><div className="flex flex-wrap gap-2"><Dialog><DialogTrigger asChild><Button size="sm" className="rounded-full bg-[#7163f6] hover:bg-[#6053e9]"><Plus className="mr-1 h-3.5 w-3.5" /> Цель</Button></DialogTrigger><DialogContent className="rounded-3xl border-0 p-7"><DialogHeader><DialogTitle className="font-display text-3xl">Назовите пункт назначения.</DialogTitle><DialogDescription>Свяжите измеримую цель с мечтой, которая придаёт ей смысл.</DialogDescription></DialogHeader><form onSubmit={event => { event.preventDefault(); createGoal.mutate({ dreamId: Number(goalDreamId), title: goalTitle }); setGoalTitle(""); }} className="mt-5 space-y-3"><select value={goalDreamId} onChange={event => setGoalDreamId(event.target.value)} required className="h-11 w-full rounded-xl border border-[#e5e1eb] bg-white px-3 text-sm"><option value="">Выберите мечту</option>{dreams.map(dream => <option key={dream.id} value={dream.id}>{dream.title}</option>)}</select><Input value={goalTitle} onChange={event => setGoalTitle(event.target.value)} placeholder="Как выглядит успех?" required className="rounded-xl" /><Button disabled={createGoal.isPending} className="w-full rounded-xl bg-[#7163f6]">Создать цель</Button></form></DialogContent></Dialog>
      <Dialog><DialogTrigger asChild><Button size="sm" variant="outline" className="rounded-full border-[#ded9e8] bg-white"><Plus className="mr-1 h-3.5 w-3.5" /> Дорожная карта</Button></DialogTrigger><DialogContent className="rounded-3xl border-0 p-7"><DialogHeader><DialogTitle className="font-display text-3xl">Проложите путь.</DialogTitle><DialogDescription>Создайте для цели последовательность значимых этапов.</DialogDescription></DialogHeader><form onSubmit={event => { event.preventDefault(); createRoadmap.mutate({ goalId: Number(roadmapGoalId), title: roadmapTitle }); setRoadmapTitle(""); }} className="mt-5 space-y-3"><select value={roadmapGoalId} onChange={event => setRoadmapGoalId(event.target.value)} required className="h-11 w-full rounded-xl border border-[#e5e1eb] bg-white px-3 text-sm"><option value="">Выберите цель</option>{goals.map(goal => <option key={goal.id} value={goal.id}>{goal.title}</option>)}</select><Input value={roadmapTitle} onChange={event => setRoadmapTitle(event.target.value)} placeholder="Например: стартовый спринт" required className="rounded-xl" /><Button disabled={createRoadmap.isPending} className="w-full rounded-xl bg-[#1f1d33]">Создать дорожную карту</Button></form></DialogContent></Dialog></div></div>
    <div className="divide-y divide-[#efecf3]">{goals.length ? goals.map(goal => <article key={goal.id} className="p-5"><div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between"><div className="flex items-center gap-3"><span className="grid h-9 w-9 place-items-center rounded-xl bg-[#f0eeff] text-[#7163f6]"><Goal className="h-4 w-4" /></span><div><h3 className="text-sm font-semibold text-[#3b374a]">{goal.title}</h3><p className="mt-0.5 text-xs text-[#908a99]">{localizedStatus(goal.status)} · {goal.targetDate ? friendlyDate(goal.targetDate) : "Дата ещё не задана"}</p></div></div><Badge className="w-fit rounded-full bg-[#edf8f2] text-[#398d6c] hover:bg-[#edf8f2]">связана с мечтой</Badge></div><div className="mt-4 space-y-3">{roadmapByGoal(goal.id).map(roadmap => <div key={roadmap.id} className="rounded-2xl bg-[#faf9fc] p-4"><div className="flex items-center gap-2"><Layers3 className="h-4 w-4 text-[#6e62ea]" /><p className="text-sm font-medium text-[#514b60]">{roadmap.title}</p></div><div className="mt-3 space-y-2 border-l border-[#dcd7ef] pl-4">{milestonesByRoadmap(roadmap.id).map(milestone => <div key={milestone.id}><div className="flex items-center gap-2 text-sm text-[#625d6c]"><span className="h-2 w-2 rounded-full bg-[#a497ff]" />{milestone.title}</div>{actionsByMilestone(milestone.id).map(action => <div key={action.id} className="ml-4 mt-1 flex items-center gap-2 text-xs text-[#938d9c]"><MoveRight className="h-3 w-3" />{action.title} · {minutes(action.estimateMinutes)}</div>)}</div>)}</div></div>)}</div></article>) : <div className="p-10 text-center"><Target className="mx-auto h-8 w-8 text-[#c4bcf6]" /><p className="mt-3 text-sm font-medium text-[#5d5769]">Выберите мечту и задайте ей направление.</p><p className="mt-1 text-xs text-[#948e9d]">Первая цель откроет её дорожную карту.</p></div>}</div>
    {roadmaps.length > 0 && <div className="grid gap-3 border-t border-[#efecf3] bg-[#fcfbfe] p-4 md:grid-cols-2"><form onSubmit={event => { event.preventDefault(); createMilestone.mutate({ roadmapId: Number(milestoneRoadmapId), title: milestoneTitle }); setMilestoneTitle(""); }} className="flex gap-2"><select value={milestoneRoadmapId} onChange={event => setMilestoneRoadmapId(event.target.value)} required className="min-w-0 flex-1 rounded-xl border border-[#e5e1eb] bg-white px-2 text-xs"><option value="">Дорожная карта</option>{roadmaps.map(roadmap => <option key={roadmap.id} value={roadmap.id}>{roadmap.title}</option>)}</select><Input value={milestoneTitle} onChange={event => setMilestoneTitle(event.target.value)} placeholder="Добавить этап" required className="min-w-0 rounded-xl text-xs" /><Button size="icon" className="shrink-0 rounded-xl bg-[#7163f6]"><Plus className="h-4 w-4" /></Button></form><form onSubmit={event => { event.preventDefault(); createAction.mutate({ milestoneId: Number(actionMilestoneId), title: actionTitle, estimateMinutes: 30 }); setActionTitle(""); }} className="flex gap-2"><select value={actionMilestoneId} onChange={event => setActionMilestoneId(event.target.value)} required className="min-w-0 flex-1 rounded-xl border border-[#e5e1eb] bg-white px-2 text-xs"><option value="">Этап</option>{milestones.map(milestone => <option key={milestone.id} value={milestone.id}>{milestone.title}</option>)}</select><Input value={actionTitle} onChange={event => setActionTitle(event.target.value)} placeholder="Добавить действие" required className="min-w-0 rounded-xl text-xs" /><Button size="icon" className="shrink-0 rounded-xl bg-[#1f1d33]"><Plus className="h-4 w-4" /></Button></form></div>}
  </section>;
}

export function CalendarView({ events, calendars, refresh }: { events: any[]; calendars: any[]; refresh: () => void }) {
  const [cursor, setCursor] = useState(() => new Date());
  const [level, setLevel] = useState<CalendarLevel>("month");
  const [history, setHistory] = useState<CalendarLevel[]>([]);
  const [filter, setFilter] = useState("all");
  const reschedule = formaApi.calendars.reschedule.useMutation({ onSuccess: refresh });
  const levelLabel = calendarLevelLabel;
  const overviewPeriods = useMemo(() => level === "year" ? [0, 3, 6, 9].map(month => new Date(cursor.getFullYear(), month, 1)) : level === "quarter" ? [0, 1, 2].map(offset => new Date(cursor.getFullYear(), Math.floor(cursor.getMonth() / 3) * 3 + offset, 1)) : [], [cursor, level]);
  const interval = useMemo(() => {
    if (level === "day") return [new Date(cursor.getFullYear(), cursor.getMonth(), cursor.getDate())];
    if (level === "week") return Array.from({ length: 7 }, (_, index) => { const day = startOfWeek(cursor); day.setDate(day.getDate() + index); return day; });
    const first = new Date(cursor.getFullYear(), cursor.getMonth(), 1); const gridStart = startOfWeek(first); return Array.from({ length: 35 }, (_, index) => { const day = new Date(gridStart); day.setDate(day.getDate() + index); return day; });
  }, [cursor, level]);
  const visibleEvents = events.filter(event => filter === "all" || String(event.calendarId) === filter);
  const navigate = (direction: number) => setCursor(moveCalendarCursor(cursor, level, direction));
  const drill = (nextLevel: CalendarLevel, date: Date) => { setHistory(previous => [...previous, level]); setLevel(nextLevel); setCursor(date); };
  const goBack = () => { const previous = history[history.length - 1] ?? calendarBackLevel(level); setHistory(items => items.slice(0, -1)); setLevel(previous); };
  const breadcrumb = calendarBreadcrumb(cursor, level);
  const heading = breadcrumb.map((segment, index) => <span key={segment.level}><button type="button" onClick={() => { setLevel(segment.level); setCursor(segment.date); setHistory([]); }} className="transition-colors hover:text-[#6259d8]">{segment.label}</button>{index < breadcrumb.length - 1 && <span className="px-1 text-[#afa8bd]">›</span>}</span>);
  const onDrop = (event: DragEvent<HTMLDivElement>, day: Date) => { event.preventDefault(); const eventId = Number(event.dataTransfer.getData("text/forma-event")); const current = events.find(item => item.id === eventId); if (!current || !eventId) return; const startsAt = new Date(day); const oldStart = new Date(current.startsAt); startsAt.setHours(oldStart.getHours(), oldStart.getMinutes(), 0, 0); const endsAt = new Date(startsAt.getTime() + (new Date(current.endsAt).getTime() - oldStart.getTime())); reschedule.mutate({ eventId, startsAt, endsAt }); };
  const eventsInPeriod = (start: Date, months: number) => { const end = new Date(start.getFullYear(), start.getMonth() + months, 1); return visibleEvents.filter(event => { const date = new Date(event.startsAt); return date >= start && date < end; }).length; };
  return <section className="surface-card overflow-hidden"><div className="flex flex-col gap-4 border-b border-[#efecf3] p-5 xl:flex-row xl:items-center xl:justify-between"><div className="flex items-center gap-3"><button onClick={goBack} disabled={level === "year" && !history.length} className="grid h-9 w-9 place-items-center rounded-full bg-[#f3f1fb] text-[#6c60ed] transition-transform hover:-translate-x-0.5 disabled:cursor-not-allowed disabled:opacity-40" aria-label="Назад"><ArrowLeft className="h-4 w-4" /></button><div><div className="flex items-center gap-2 text-[10px] font-semibold uppercase tracking-[.14em] text-[#9992a5]"><span>Календарь</span><ChevronRight className="h-3 w-3" /><span className="text-[#7568ee]">{levelLabel[level]}</span></div><h2 className="mt-1 font-display text-2xl tracking-[-.04em] text-[#302c42]">{heading}</h2></div></div><div className="flex flex-wrap items-center gap-2"><div className="flex rounded-full bg-[#f3f1f7] p-1">{(["year", "quarter", "month", "week", "day"] as const).map(item => <button key={item} onClick={() => setLevel(item)} className={cn("rounded-full px-3 py-1.5 text-xs capitalize transition-all", level === item ? "bg-white font-medium text-[#443b9a] shadow-sm" : "text-[#807a8b]")}>{levelLabel[item]}</button>)}</div><select value={filter} onChange={event => setFilter(event.target.value)} className="h-8 rounded-full border border-[#e4e0eb] bg-white px-3 text-xs text-[#6e6879] outline-none"><option value="all">Все календари</option>{calendars.map(calendar => <option key={calendar.id} value={calendar.id}>{calendar.name}</option>)}</select><button onClick={() => navigate(-1)} className="calendar-nav"><ChevronLeft className="h-4 w-4" /></button><button onClick={() => navigate(1)} className="calendar-nav"><ChevronRight className="h-4 w-4" /></button></div></div>{(level === "year" || level === "quarter") ? <div className="grid gap-3 p-5 sm:grid-cols-2 lg:grid-cols-4">{overviewPeriods.map(period => { const isYear = level === "year"; const count = eventsInPeriod(period, isYear ? 3 : 1); const title = isYear ? `${Math.floor(period.getMonth() / 3) + 1} квартал` : friendlyDate(period, { month: "long" }); return <button key={period.toISOString()} onClick={() => drill(isYear ? "quarter" : "month", period)} className="rounded-2xl border border-[#ece8f2] bg-[#fcfbfe] p-5 text-left transition-colors hover:border-[#cfc8ff] hover:bg-[#f7f5ff]"><p className="text-xs font-semibold uppercase tracking-[.12em] text-[#7568ee]">{title}</p><p className="mt-2 font-display text-2xl text-[#343044]">{count}</p><p className="mt-1 text-xs text-[#8b8597]">{count === 1 ? "событие" : "событий"}</p><p className="mt-4 text-xs font-medium text-[#6259d8]">Открыть детали →</p></button>; })}</div> : <><div className={cn("calendar-grid", level === "day" ? "grid-cols-1" : "grid-cols-7")}>{level !== "day" && ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"].map(day => <div key={day} className="calendar-weekday">{day}</div>)}{interval.map(day => { const dayEvents = visibleEvents.filter(event => dateKey(event.startsAt) === dateKey(day)); const isMuted = level === "month" && day.getMonth() !== cursor.getMonth(); const isToday = dateKey(day) === dateKey(new Date()); return <div key={day.toISOString()} onDragOver={event => event.preventDefault()} onDrop={event => onDrop(event, day)} className={cn("calendar-cell", level === "day" && "min-h-[400px]", isMuted && "opacity-40")}><button onClick={() => level === "month" ? drill("week", day) : level === "week" ? drill("day", day) : undefined} className={cn("calendar-date", isToday && "calendar-date-today")}>{level === "day" ? friendlyDate(day, { weekday: "long", month: "long", day: "numeric" }) : day.getDate()}</button><div className="mt-2 space-y-1.5">{dayEvents.map(event => { const calendar = calendars.find(item => item.id === event.calendarId); return <div key={event.id} draggable onDragStart={drag => drag.dataTransfer.setData("text/forma-event", String(event.id))} className="calendar-event" style={{ "--event-color": calendar?.color ?? "#7163f6" } as React.CSSProperties}><GripVertical className="h-3 w-3 shrink-0 opacity-40" /><span className="truncate">{event.title}</span></div>; })}{level === "day" && !dayEvents.length && <p className="px-2 py-8 text-center text-sm text-[#aaa4b1]">Перетащите сюда запланированный блок.</p>}</div></div>; })}</div><div className="flex items-center gap-5 border-t border-[#efecf3] px-5 py-3 text-[11px] text-[#938d9c]"><span className="flex items-center gap-1.5"><span className="h-2 w-2 rounded-full bg-[#7163f6]" /> Перетащите блок, чтобы изменить время</span><span>Нажмите дату, чтобы перейти к деталям</span></div></>}</section>;
}

function FlowMap({ dreams, goals, roadmaps, milestones, actions, tasks, calendars }: { dreams: any[]; goals: any[]; roadmaps: any[]; milestones: any[]; actions: any[]; tasks: any[]; calendars: any[] }) {
  const [mode, setMode] = useState<"map" | "timeline" | "list">("map");
  const roadmapById = new globalThis.Map(roadmaps.map(roadmap => [roadmap.id, roadmap]));
  const milestoneById = new globalThis.Map(milestones.map(milestone => [milestone.id, milestone]));
  const actionById = new globalThis.Map(actions.map(action => [action.id, action]));
  const nodes = [
    ...dreams.slice(0, 1).map(dream => ({ id: `dream-${dream.id}`, parentId: undefined as string | undefined, label: dream.title, type: "Dream", color: colorFromVisual(dream.visualConfig), size: "large" })),
    ...goals.slice(0, 2).map(goal => ({ id: `goal-${goal.id}`, parentId: `dream-${goal.dreamId}`, label: goal.title, type: "Goal", color: "#4f83f7", size: "medium" })),
    ...tasks.slice(0, 4).map(task => {
      const action = task.actionId ? actionById.get(task.actionId) : undefined;
      const milestone = task.milestoneId ? milestoneById.get(task.milestoneId) : action?.milestoneId ? milestoneById.get(action.milestoneId) : undefined;
      const roadmap = milestone ? roadmapById.get(milestone.roadmapId) : undefined;
      const parentId = task.parentId ? `task-${task.parentId}` : action?.goalId ? `goal-${action.goalId}` : roadmap ? `goal-${roadmap.goalId}` : undefined;
      return { id: `task-${task.id}`, parentId, label: task.title, type: "Task", color: task.priority === "critical" ? "#ff7a62" : task.priority === "high" ? "#f6ad55" : "#7568ee", size: task.priority === "critical" ? "medium" : "small" };
    }),
  ];
  const positions = [{ x: 6, y: 38 }, { x: 38, y: 12 }, { x: 39, y: 64 }, { x: 72, y: 18 }, { x: 74, y: 65 }];
  const positioned = nodes.slice(0, 5).map((node, index) => ({ ...node, position: positions[index] ?? positions[0] }));
  const edges = positioned.flatMap(node => { const parent = positioned.find(candidate => candidate.id === node.parentId); return parent ? [{ from: parent, to: node }] : []; });
  return <section className="surface-card overflow-hidden"><div className="flex flex-col gap-4 border-b border-[#efecf3] p-5 sm:flex-row sm:items-center sm:justify-between"><div><p className="text-sm font-semibold text-[#343044]">Карта связей</p><p className="mt-0.5 text-xs text-[#8a8595]">Связи рассчитываются по вашим реальным мечтам, целям и задачам.</p></div><div className="flex rounded-full bg-[#f3f1f7] p-1">{(["map", "timeline", "list"] as const).map(item => <button key={item} onClick={() => setMode(item)} className={cn("rounded-full px-3 py-1.5 text-xs capitalize transition-all", mode === item ? "bg-white font-medium text-[#443b9a] shadow-sm" : "text-[#807a8b]")}>{item === "map" ? "карта" : item === "timeline" ? "хронология" : "список"}</button>)}</div></div>{mode === "map" ? <div className="flow-canvas">{positioned.length ? <><svg className="pointer-events-none absolute inset-0 h-full w-full">{edges.map(edge => <line key={`${edge.from.id}-${edge.to.id}`} x1={`${edge.from.position.x + 12}%`} y1={`${edge.from.position.y + 10}%`} x2={`${edge.to.position.x + 8}%`} y2={`${edge.to.position.y + 10}%`} stroke="#b8b0eb" strokeWidth="2" strokeDasharray="4 4" />)}</svg>{positioned.map(node => <article key={node.id} className={cn("flow-node", `node-${node.size}`)} style={{ "--node-color": node.color, left: `${node.position.x}%`, top: `${node.position.y}%` } as React.CSSProperties}><span className="flow-node-type">{node.type === "Dream" ? "Мечта" : node.type === "Goal" ? "Цель" : "Задача"}</span><p>{node.label}</p>{node.type === "Task" && <span className="flow-node-meta">{calendars[0]?.name ?? "Личный"}</span>}</article>)}</> : <div className="grid h-full place-items-center text-center"><MapIcon className="mx-auto h-7 w-7 text-[#b3acf1]" /><p className="mt-3 text-sm text-[#78728a]">Здесь появится ваша первая связь.</p></div>}</div> : <div className="p-5">{positioned.length ? positioned.map((node, index) => <div key={node.id} className="flex items-center gap-4 border-b border-[#f0edf3] py-3 last:border-0"><span className="grid h-8 w-8 place-items-center rounded-full text-xs font-semibold text-white" style={{ background: node.color }}>{index + 1}</span><div className="flex-1"><p className="text-sm font-medium text-[#3d394c]">{node.label}</p><p className="mt-0.5 text-xs text-[#918b99]">{node.type === "Dream" ? "Мечта" : node.type === "Goal" ? "Цель" : "Задача"} · {node.parentId ? "связано с родительским элементом" : "исходная точка"}</p></div><MoveRight className="h-4 w-4 text-[#b1abb7]" /></div>) : <p className="py-12 text-center text-sm text-[#9993a2]">Создайте мечту, цель или задачу, чтобы начать строить карту.</p>}</div>}</section>;
}

function Assistant({ refresh }: { refresh: () => void }) {
  const [intent, setIntent] = useState("");
  const [proposal, setProposal] = useState<{ id: string; summary: string; commands: PlanCommand[] } | null>(null);
  const propose = formaApi.ai.propose.useMutation({ onSuccess: response => { setProposal({ id: response.plan.id, ...response.proposal }); refresh(); } });
  const approve = formaApi.ai.approve.useMutation({ onSuccess: () => { refresh(); setProposal(null); } });
  const submit = (event: FormEvent) => { event.preventDefault(); propose.mutate({ intent }); };
  return <section className="assistant-panel overflow-hidden"><div className="relative z-10 max-w-2xl"><div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-white/15 text-[#dcd7ff]"><Sparkles className="h-5 w-5" /></div><p className="mt-7 text-xs font-semibold uppercase tracking-[.16em] text-[#bbb3f2]">ИНТЕЛЛЕКТ FORMA</p><h2 className="mt-3 font-display text-4xl tracking-[-.055em] text-white">Превратите ощущение в план.</h2><p className="mt-3 max-w-xl text-sm leading-6 text-[#d0cce3]">Опишите, к чему хотите двигаться. Forma вернёт структурированное предложение для просмотра — ничего не изменится без вашего подтверждения.</p><form onSubmit={submit} className="mt-7 flex flex-col gap-3 sm:flex-row"><Textarea value={intent} onChange={event => setIntent(event.target.value)} placeholder="Хочу выстроить более устойчивый ритм заботы о здоровье…" className="min-h-14 resize-none rounded-2xl border-white/10 bg-white/10 px-4 py-3 text-white placeholder:text-[#aaa4c4] focus-visible:ring-[#b8afff]" required /><Button disabled={propose.isPending} className="h-auto shrink-0 rounded-2xl bg-[#f0edff] px-5 text-[#372e76] hover:bg-white">{propose.isPending ? "Размышляем…" : "Создать предложение"} <ArrowRight className="ml-2 h-4 w-4" /></Button></form><p className="mt-4 text-[11px] text-[#aaa3ca]">Доступны только цели, дорожные карты, задачи и предложения календарных слотов.</p></div><div className="assistant-glow" />{proposal && <div className="relative z-10 mt-8 rounded-3xl bg-white p-5 text-[#343047] shadow-2xl"><div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between"><div><p className="text-xs font-semibold uppercase tracking-[.13em] text-[#766aec]">Предложение готово к просмотру</p><p className="mt-1 text-sm leading-6 text-[#686277]">{proposal.summary}</p></div><Badge className="w-fit rounded-full bg-[#f0eeff] text-[#6659df] hover:bg-[#f0eeff]">Изменения не применены</Badge></div><div className="mt-4 space-y-2">{proposal.commands.map((command, index) => <div key={`${command.title}-${index}`} className="flex gap-3 rounded-2xl bg-[#faf9fc] p-3"><span className={cn("grid h-7 w-7 shrink-0 place-items-center rounded-lg text-[10px] font-bold", commandTone[command.command])}>{index + 1}</span><div><p className="text-sm font-medium">{command.title}</p><p className="mt-0.5 text-xs leading-5 text-[#858090]">{command.description}</p><span className="mt-1.5 inline-block text-[10px] font-medium uppercase tracking-[.1em] text-[#8d86a7]">{commandLabel[command.command]}</span></div></div>)}</div><div className="mt-5 flex flex-wrap gap-2"><Button onClick={() => approve.mutate({ aiPlanId: proposal.id, idempotencyKey: randomKey() })} disabled={approve.isPending} className="rounded-xl bg-[#7163f6] hover:bg-[#6053e9]"><Check className="mr-1.5 h-4 w-4" />{approve.isPending ? "Применяем…" : "Утвердить и применить"}</Button><Button onClick={() => setProposal(null)} variant="outline" className="rounded-xl border-[#e5e1ec]">Продолжить планирование</Button></div></div>}</section>;
}

function Dashboard() {
  const [location] = useLocation();
  const view = (location.slice(1).split("?")[0] || "today") as ViewName;
  const currentView = viewCopy[view] ? view : "today";
  const [workspaceName, setWorkspaceName] = useState("Моё пространство Forma");
  const createWorkspace = formaApi.workspaces.create.useMutation({
    onSuccess: workspace => {
      window.localStorage.setItem("forma_workspace_id", workspace.id);
      window.location.reload();
    },
  });
  const overview = formaApi.overview.useQuery();
  const data = overview.data;
  const refresh = () => overview.refetch();
  if (!window.localStorage.getItem("forma_workspace_id")) return <DashboardLayout><section className="mx-auto grid min-h-[70vh] max-w-lg place-items-center"><form onSubmit={event => { event.preventDefault(); createWorkspace.mutate({ name: workspaceName }); }} className="surface-card w-full p-8 text-center"><span className="mx-auto grid h-12 w-12 place-items-center rounded-2xl bg-[#f0eeff] text-[#7163f6]"><Sparkles className="h-5 w-5" /></span><p className="mt-5 font-display text-3xl tracking-[-.04em] text-[#302c42]">Начните со своего пространства.</p><p className="mx-auto mt-3 max-w-sm text-sm leading-6 text-[#847e91]">Forma хранит каждую мечту, цель и задачу внутри вашего личного пространства.</p><Input value={workspaceName} onChange={event => setWorkspaceName(event.target.value)} className="mt-6 rounded-xl" required /><Button disabled={createWorkspace.isPending} className="mt-3 w-full rounded-xl bg-[#7163f6] hover:bg-[#6053e9]">{createWorkspace.isPending ? "Создаём…" : "Создать пространство Forma"}</Button></form></section></DashboardLayout>;
  if (overview.isLoading || !data) return <DashboardLayout><div className="grid min-h-[70vh] place-items-center"><div className="flex items-center gap-3 text-sm text-[#777184]"><span className="h-3 w-3 animate-pulse rounded-full bg-[#7163f6]" /> Открываем пространство Forma…</div></div></DashboardLayout>;
  const completed = data.tasks.filter(task => task.status === "done").length;
  const estimate = data.tasks.reduce((total, task) => total + task.estimateMinutes, 0);
  const actual = data.timeEntries.reduce((total, entry) => total + Math.round(entry.durationSeconds / 60), 0);
  const unread = data.notifications.filter(notification => !notification.readAt).length;
  const activeEntry = data.timeEntries.find(entry => !entry.endedAt);
  return <DashboardLayout><div className="mx-auto max-w-[1480px] space-y-7"><WorkspaceHeader view={currentView} workspaceName={data.workspace.name} unread={unread} />
    {currentView === "today" && <><section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4"><Stat icon={Target} label="Цели в движении" value={String(data.goals.filter(goal => goal.status === "active").length)} detail="Связаны с вашим направлением" accent="bg-[#f0eeff] text-[#7163f6]" /><Stat icon={CheckCircle2} label="Задачи выполнены" value={`${completed}/${data.tasks.length}`} detail={data.tasks.length ? "Небольшой прогресс накапливается" : "Начните с одного ясного шага"} accent="bg-[#e9f8f1] text-[#319d71]" /><Stat icon={Clock3} label="Вложенное время" value={minutes(actual)} detail={`из ${minutes(estimate)} запланированных`} accent="bg-[#fff3e9] text-[#e6893a]" /><Stat icon={Flame} label="Текущий фокус" value={activeEntry ? "Активен" : "Готов"} detail={activeEntry ? "Таймер защищает ваше внимание" : "Выберите следующий блок"} accent="bg-[#fff0ed] text-[#e36f5e]" /></section><section className="grid gap-5 xl:grid-cols-[1.25fr_.75fr]"><div className="space-y-5"><CalendarView events={data.events} calendars={data.calendars} refresh={refresh} /><TaskList tasks={data.tasks} timeEntries={data.timeEntries} refresh={refresh} /></div><div className="space-y-5"><div className="flex items-center justify-between"><div><p className="font-display text-2xl tracking-[-.04em] text-[#302c42]">Главный ориентир</p><p className="mt-1 text-xs text-[#938d9c]">Напоминание, ради чего всё это движется.</p></div><CreateDream onCreated={refresh} /></div><DreamCards dreams={data.dreams} /></div></section><section className="grid gap-5 xl:grid-cols-[.8fr_1.2fr]"><Assistant refresh={refresh} /><FlowMap dreams={data.dreams} goals={data.goals} roadmaps={data.roadmaps} milestones={data.milestones} actions={data.actions} tasks={data.tasks} calendars={data.calendars} /></section></>}
    {currentView === "dreams" && <section className="space-y-5"><div className="flex justify-end"><CreateDream onCreated={refresh} /></div><div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">{data.dreams.map(dream => <article key={dream.id} className="dream-card min-h-64" style={{ background: `linear-gradient(135deg, ${colorFromVisual(dream.visualConfig)}, #29243f 120%)` }}><div className="relative z-10"><Badge className="rounded-full bg-white/15 text-white hover:bg-white/15">{localizedStatus(dream.status)}</Badge><h2 className="mt-14 font-display text-3xl tracking-[-.045em] text-white">{dream.title}</h2><p className="mt-3 max-w-sm text-sm leading-6 text-white/70">{dream.description || "Значимое направление, ожидающее первого шага."}</p></div><div className="absolute bottom-5 left-5 flex items-center gap-2 text-xs text-white/70"><Diamond className="h-4 w-4" /> Видение Forma</div></article>)}{!data.dreams.length && <div className="col-span-full rounded-3xl border border-dashed border-[#ded9e8] bg-white/60 py-20 text-center"><Lightbulb className="mx-auto h-9 w-9 text-[#9a8eee]" /><h3 className="mt-4 font-display text-2xl text-[#423c52]">Какому будущему вы хотите дать место?</h3><p className="mx-auto mt-2 max-w-md text-sm text-[#8b8595]">Создайте мечту, затем свяжите её с целью и планом, к которому можно приступить сегодня.</p></div>}</div><GoalStudio dreams={data.dreams} goals={data.goals} roadmaps={data.roadmaps} milestones={data.milestones} actions={data.actions} refresh={refresh} /></section>}
    {currentView === "calendar" && <section className="space-y-5"><div className="flex flex-wrap justify-end gap-2"><CreateCalendar onCreated={refresh} /><CreateTask tasks={data.tasks} actions={data.actions} milestones={data.milestones} onCreated={refresh} /><ScheduleBlock tasks={data.tasks} calendars={data.calendars} onScheduled={refresh} /></div><CalendarView events={data.events} calendars={data.calendars} refresh={refresh} /></section>}
    {currentView === "flow" && <section className="grid gap-5 xl:grid-cols-[1.25fr_.75fr]"><FlowMap dreams={data.dreams} goals={data.goals} roadmaps={data.roadmaps} milestones={data.milestones} actions={data.actions} tasks={data.tasks} calendars={data.calendars} /><div className="space-y-5"><TaskList tasks={data.tasks} timeEntries={data.timeEntries} refresh={refresh} /><CreateTask tasks={data.tasks} actions={data.actions} milestones={data.milestones} onCreated={refresh} /></div></section>}
    {currentView === "assistant" && <section className="space-y-5"><Assistant refresh={refresh} /><section className="surface-card p-5"><div className="flex items-center justify-between"><div><p className="text-sm font-semibold text-[#353044]">Уведомления</p><p className="mt-1 text-xs text-[#8d8797]">Предложения AI для подтверждения и календарные рекомендации появятся здесь.</p></div><Bell className="h-5 w-5 text-[#7163f6]" /></div><div className="mt-5 space-y-2">{data.notifications.length ? data.notifications.slice(0, 5).map(notification => { const copy = localizedNotification(notification); return <article key={notification.id} className="rounded-2xl bg-[#faf9fc] p-3"><p className="text-sm font-medium text-[#474153]">{copy.title}</p><p className="mt-1 text-xs leading-5 text-[#898393]">{copy.body}</p></article>; }) : <p className="py-7 text-center text-sm text-[#9993a2]">Forma покажет здесь предложения для планирования.</p>}</div></section></section>}
  </div></DashboardLayout>;
}

export default function Home() {
  const { isAuthenticated, loading } = useAuth();
  if (loading) return <div className="landing-shell grid min-h-screen place-items-center"><div className="h-3 w-3 animate-pulse rounded-full bg-[#7163f6]" /></div>;
  return isAuthenticated ? <Dashboard /> : <Landing />;
}
