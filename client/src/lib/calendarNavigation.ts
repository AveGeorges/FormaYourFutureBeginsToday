export type CalendarLevel = "year" | "quarter" | "month" | "week" | "day";

export const calendarLevelLabel: Record<CalendarLevel, string> = {
  year: "год",
  quarter: "квартал",
  month: "месяц",
  week: "неделя",
  day: "день",
};

const levelOrder: CalendarLevel[] = ["year", "quarter", "month", "week", "day"];

export function calendarBackLevel(level: CalendarLevel): CalendarLevel {
  const index = levelOrder.indexOf(level);
  return levelOrder[Math.max(0, index - 1)] ?? "year";
}

export function moveCalendarCursor(cursor: Date, level: CalendarLevel, direction: number): Date {
  const next = new Date(cursor);
  if (level === "year") next.setFullYear(next.getFullYear() + direction);
  else if (level === "quarter") next.setMonth(next.getMonth() + direction * 3);
  else next.setDate(next.getDate() + (level === "month" ? direction * 31 : level === "week" ? direction * 7 : direction));
  return next;
}

export function calendarBreadcrumb(cursor: Date, level: CalendarLevel) {
  const quarterStart = new Date(cursor.getFullYear(), Math.floor(cursor.getMonth() / 3) * 3, 1);
  const month = new Intl.DateTimeFormat("ru-RU", { month: "short" }).format(cursor);
  const day = new Intl.DateTimeFormat("ru-RU", { day: "numeric" }).format(cursor);
  return [
    { level: "year" as const, label: String(cursor.getFullYear()), date: new Date(cursor.getFullYear(), 0, 1) },
    { level: "quarter" as const, label: `${Math.floor(cursor.getMonth() / 3) + 1} кв.`, date: quarterStart },
    { level: "month" as const, label: month, date: new Date(cursor.getFullYear(), cursor.getMonth(), 1) },
    { level: "week" as const, label: "Неделя", date: startOfWeek(cursor) },
    { level: "day" as const, label: day, date: new Date(cursor.getFullYear(), cursor.getMonth(), cursor.getDate()) },
  ].slice(0, levelOrder.indexOf(level) + 1);
}

function startOfWeek(date: Date) {
  const next = new Date(date);
  const weekday = (next.getDay() + 6) % 7;
  next.setDate(next.getDate() - weekday);
  next.setHours(0, 0, 0, 0);
  return next;
}
