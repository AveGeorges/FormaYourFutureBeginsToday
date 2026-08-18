import { describe, expect, it } from "vitest";

import { calendarBackLevel, calendarBreadcrumb, moveCalendarCursor } from "./calendarNavigation";

describe("calendar multi-level navigation", () => {
  it("builds a contextual Russian breadcrumb from year to day", () => {
    const cursor = new Date(2026, 7, 18, 12, 0);

    expect(calendarBreadcrumb(cursor, "year").map(item => item.label)).toEqual(["2026"]);
    expect(calendarBreadcrumb(cursor, "quarter").map(item => item.label)).toEqual(["2026", "3 кв."]);
    expect(calendarBreadcrumb(cursor, "day").map(item => item.label)).toEqual([
      "2026", "3 кв.", "авг.", "Неделя", "18",
    ]);
  });

  it("moves cursor at the selected scale and backs out one level at a time", () => {
    const cursor = new Date(2026, 7, 18);

    expect(moveCalendarCursor(cursor, "year", 1).getFullYear()).toBe(2027);
    expect(moveCalendarCursor(cursor, "quarter", -1).getMonth()).toBe(4);
    expect(moveCalendarCursor(cursor, "week", 1).getDate()).toBe(25);
    expect(calendarBackLevel("day")).toBe("week");
    expect(calendarBackLevel("quarter")).toBe("year");
    expect(calendarBackLevel("year")).toBe("year");
  });
});
