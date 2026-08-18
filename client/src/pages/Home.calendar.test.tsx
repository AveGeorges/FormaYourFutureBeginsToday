// @vitest-environment jsdom

import { fireEvent, render, screen } from "@testing-library/react";
import React from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/lib/formaApi", () => ({
  formaApi: {
    calendars: {
      reschedule: {
        useMutation: () => ({ mutate: vi.fn() }),
      },
    },
  },
}));

import { CalendarView } from "./Home";

describe("CalendarView multi-level navigation", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date(2026, 0, 15, 12, 0));
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("drills from year to day, supports Back and navigates through a breadcrumb segment", () => {
    render(<CalendarView events={[]} calendars={[]} refresh={vi.fn()} />);

    fireEvent.click(screen.getByRole("button", { name: "год" }));
    expect(screen.getByRole("heading", { name: "2026" })).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: /1 квартал/i }));
    expect(screen.getByRole("heading", { name: /2026.*1 кв\./ })).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: /январь/i }));
    expect(screen.getByRole("heading", { name: /2026.*1 кв\..*янв\./ })).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: "15" }));
    expect(screen.getByRole("heading", { name: /2026.*1 кв\..*янв\..*Неделя/ })).toBeTruthy();

    const weekDates = screen.getAllByRole("button", { name: "15" });
    fireEvent.click(weekDates.at(-1) as HTMLButtonElement);
    expect(screen.getByRole("heading", { name: /2026.*1 кв\..*янв\..*Неделя.*15/ })).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: "Назад" }));
    expect(screen.getByRole("heading", { name: /Неделя$/ })).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: "1 кв." }));
    expect(screen.getByRole("heading", { name: /2026.*1 кв\./ })).toBeTruthy();
  });
});
