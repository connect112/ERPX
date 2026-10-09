import {
  addDays,
  addMonths,
  addWeeks,
  eachDayOfInterval,
  endOfMonth,
  endOfWeek,
  format,
  isSameMonth,
  parseISO,
  startOfMonth,
  startOfWeek,
} from "date-fns";
import { ChevronLeft, ChevronRight } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import type { CalendarItem } from "@/features/social-media/api/social-media-api";
import { useCalendar } from "@/features/social-media/api/social-media-hooks";
import { ScheduleDialog } from "@/features/social-media/components/schedule-dialog";
import { FORMAT_LABEL, STATUS_LABEL, STATUS_VARIANT } from "@/features/social-media/lib/format";

type View = "month" | "week" | "day";
const WEEK = { weekStartsOn: 1 as const };
const DOT: Record<string, string> = {
  draft: "bg-slate-400",
  review: "bg-blue-500",
  approved: "bg-emerald-500",
  scheduled: "bg-indigo-500",
  publishing: "bg-indigo-500",
  published: "bg-emerald-700",
  failed: "bg-red-500",
  cancelled: "bg-slate-300",
  publish_unknown: "bg-amber-500",
};

const key = (d: Date) => format(d, "yyyy-MM-dd");

function today(timeZone: string): Date {
  const parts = new Intl.DateTimeFormat("sv-SE", { timeZone }).format(new Date());
  return parseISO(parts);
}

function ItemLine({ item, onOpen, showTime = true }: { item: CalendarItem; onOpen: (id: string) => void; showTime?: boolean }) {
  return (
    <button
      type="button"
      onClick={() => onOpen(item.id)}
      className="flex w-full items-center gap-1.5 rounded px-1 py-0.5 text-left text-xs hover:bg-accent"
      title={`${item.title} (${STATUS_LABEL[item.status]})`}
    >
      <span className={`h-2 w-2 shrink-0 rounded-full ${DOT[item.status] ?? "bg-slate-400"}`} aria-hidden />
      {showTime && <span className="shrink-0 text-muted-foreground">{item.local_time}</span>}
      <span className="truncate">{item.title}</span>
    </button>
  );
}

/** Posts by their planned or scheduled time in the account timezone, in month, week and day views. */
export function CalendarTab() {
  const [view, setView] = useState<View>("month");
  const [zone, setZone] = useState("Asia/Kolkata");
  const [cursor, setCursor] = useState<Date | null>(null);
  const [openId, setOpenId] = useState<string | null>(null);

  const anchor = cursor ?? today(zone);
  const range = useMemo(() => {
    if (view === "month") return { start: startOfWeek(startOfMonth(anchor), WEEK), end: endOfWeek(endOfMonth(anchor), WEEK) };
    if (view === "week") return { start: startOfWeek(anchor, WEEK), end: endOfWeek(anchor, WEEK) };
    return { start: anchor, end: anchor };
  }, [view, anchor]);
  const calendar = useCalendar(key(range.start), key(range.end));
  useEffect(() => {
    if (calendar.data) setZone(calendar.data.timezone);
  }, [calendar.data]);

  const byDay = useMemo(() => {
    const map = new Map<string, CalendarItem[]>();
    for (const item of calendar.data?.items ?? []) map.set(item.local_date, [...(map.get(item.local_date) ?? []), item]);
    return map;
  }, [calendar.data]);
  const days = eachDayOfInterval(range);
  const todayKey = key(today(zone));

  function move(step: number) {
    setCursor(view === "month" ? addMonths(anchor, step) : view === "week" ? addWeeks(anchor, step) : addDays(anchor, step));
  }

  const title = view === "month" ? format(anchor, "MMMM yyyy") : view === "week" ? `${format(range.start, "d MMM")} to ${format(range.end, "d MMM yyyy")}` : format(anchor, "EEEE d MMMM yyyy");

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2">
        <Button variant="outline" size="icon" aria-label="Previous" onClick={() => move(-1)}>
          <ChevronLeft className="h-4 w-4" />
        </Button>
        <Button variant="outline" size="icon" aria-label="Next" onClick={() => move(1)}>
          <ChevronRight className="h-4 w-4" />
        </Button>
        <Button variant="outline" onClick={() => setCursor(null)}>
          Today
        </Button>
        <h2 className="mx-2 text-lg font-semibold">{title}</h2>
        <div className="flex-1" />
        <div className="flex rounded-md border p-0.5" role="group" aria-label="Calendar view">
          {(["month", "week", "day"] as View[]).map((v) => (
            <Button key={v} size="sm" variant={view === v ? "default" : "ghost"} onClick={() => setView(v)} aria-pressed={view === v}>
              {v[0].toUpperCase() + v.slice(1)}
            </Button>
          ))}
        </div>
      </div>
      <p className="text-xs text-muted-foreground">
        Times are in the account timezone ({zone}). Drafts with a planned time are shown too, so you can see gaps and clusters before anything is scheduled.
      </p>

      {calendar.isLoading ? (
        <Skeleton className="h-96 w-full" />
      ) : calendar.isError ? (
        <p className="text-sm text-destructive">Couldn&apos;t load the calendar.</p>
      ) : view === "day" ? (
        <Card>
          <CardContent className="space-y-2 p-4">
            {(byDay.get(key(anchor)) ?? []).length === 0 ? (
              <p className="text-sm text-muted-foreground">Nothing planned for this day.</p>
            ) : (
              (byDay.get(key(anchor)) ?? []).map((item) => (
                <button key={item.id} type="button" onClick={() => setOpenId(item.id)} className="flex w-full items-center gap-3 rounded-md border p-2 text-left hover:bg-accent">
                  {item.thumbnail ? <img src={item.thumbnail} alt="" className="h-16 w-12 rounded border object-cover" loading="lazy" /> : <div className="h-16 w-12 rounded border bg-muted" aria-hidden />}
                  <div className="min-w-0 flex-1">
                    <p className="truncate font-medium">
                      {item.local_time} · {item.title}
                    </p>
                    <p className="text-xs text-muted-foreground">
                      {FORMAT_LABEL[item.format]}
                      {item.pillar ? ` · ${item.pillar}` : ""}
                    </p>
                  </div>
                  <Badge variant={STATUS_VARIANT[item.status]}>{STATUS_LABEL[item.status]}</Badge>
                </button>
              ))
            )}
          </CardContent>
        </Card>
      ) : (
        <div className="overflow-x-auto">
          <div className="grid min-w-[42rem] grid-cols-7 gap-px rounded-md border bg-border">
            {days.slice(0, 7).map((d) => (
              <div key={key(d)} className="bg-muted/50 p-1.5 text-center text-xs font-medium">
                {format(d, "EEE")}
              </div>
            ))}
            {days.map((d) => {
              const items = byDay.get(key(d)) ?? [];
              const limit = view === "month" ? 3 : 12;
              const dim = view === "month" && !isSameMonth(d, anchor);
              return (
                <div key={key(d)} className={`min-h-24 space-y-0.5 bg-background p-1.5 ${dim ? "opacity-50" : ""}`}>
                  <button
                    type="button"
                    onClick={() => {
                      setCursor(d);
                      setView("day");
                    }}
                    className={`text-xs ${key(d) === todayKey ? "rounded bg-primary px-1.5 font-semibold text-primary-foreground" : "text-muted-foreground"}`}
                    aria-label={`Open ${format(d, "d MMMM")}`}
                  >
                    {format(d, "d")}
                  </button>
                  {items.slice(0, limit).map((item) => (
                    <ItemLine key={item.id} item={item} onOpen={setOpenId} />
                  ))}
                  {items.length > limit && <p className="px-1 text-[11px] text-muted-foreground">+{items.length - limit} more</p>}
                </div>
              );
            })}
          </div>
        </div>
      )}

      <Card>
        <CardHeader>
          <CardTitle>Approved, not scheduled yet</CardTitle>
          <CardDescription>
            {calendar.data?.publish_mode === "scheduled"
              ? "Pick a time for these, or publish them now."
              : "Scheduling is switched off, so these are published by hand: open one and use Publish now."}
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-1">
          {(calendar.data?.ready_to_schedule ?? []).length === 0 ? (
            <p className="text-sm text-muted-foreground">Nothing is waiting.</p>
          ) : (
            calendar.data?.ready_to_schedule.map((item) => (
              <div key={item.id} className="flex items-center justify-between gap-2 rounded-md border p-2 text-sm">
                <span className="truncate">{item.title}</span>
                <Button size="sm" variant="outline" onClick={() => setOpenId(item.id)}>
                  {calendar.data?.publish_mode === "scheduled" ? "Schedule" : "Open"}
                </Button>
              </div>
            ))
          )}
        </CardContent>
      </Card>

      <ScheduleDialog postId={openId} onOpenChange={(open) => !open && setOpenId(null)} />
    </div>
  );
}
