import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import type { HackathonPublic } from "@/features/hackathons/api/hackathons-api";
import { useUpdateHackathon } from "@/features/hackathons/api/hackathons-hooks";
import { pad2, splitDuration, timerState } from "@/features/hackathons/lib/countdown";

function errorMessage(error: unknown, fallback: string): string {
  const message = (error as { response?: { data?: { error?: { message?: string } } } })?.response?.data?.error
    ?.message;
  return message ?? fallback;
}

/** An ISO moment as the value of a date-and-time input (in this browser's timezone). */
function toInput(iso: string | null): string {
  if (!iso) return "";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  return `${d.getFullYear()}-${pad2(d.getMonth() + 1)}-${pad2(d.getDate())}T${pad2(d.getHours())}:${pad2(d.getMinutes())}`;
}

/** What the date-and-time input holds, as an ISO moment (null when empty). */
function fromInput(value: string): string | null {
  if (!value) return null;
  const d = new Date(value);
  return Number.isNaN(d.getTime()) ? null : d.toISOString();
}

function longForm(value: string): string {
  const d = new Date(value);
  return Number.isNaN(d.getTime())
    ? ""
    : d.toLocaleString(undefined, {
        weekday: "long",
        day: "numeric",
        month: "long",
        year: "numeric",
        hour: "numeric",
        minute: "2-digit",
      });
}

/**
 * The event's timer: pick when it starts (optional) and when it ends, by day, date and time. It runs by itself
 * on the presentation page and on participants' hackathon page (counting down to the start, then to the end).
 * It is only a display: it does not open or close anything.
 */
export function EventTimerCard({ hackathon }: { hackathon: HackathonPublic }) {
  const update = useUpdateHackathon(hackathon.id);
  const [start, setStart] = useState(toInput(hackathon.timer_starts_at));
  const [end, setEnd] = useState(toInput(hackathon.timer_ends_at));
  const [now, setNow] = useState(() => Date.now());

  useEffect(() => {
    setStart(toInput(hackathon.timer_starts_at));
    setEnd(toInput(hackathon.timer_ends_at));
  }, [hackathon.timer_starts_at, hackathon.timer_ends_at]);

  useEffect(() => {
    const timer = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(timer);
  }, []);

  const startIso = fromInput(start);
  const endIso = fromInput(end);
  const order = startIso && endIso && Date.parse(endIso) <= Date.parse(startIso) ? "The timer must end after it starts." : null;
  const changed = startIso !== (hackathon.timer_starts_at ? new Date(hackathon.timer_starts_at).toISOString() : null) ||
    endIso !== (hackathon.timer_ends_at ? new Date(hackathon.timer_ends_at).toISOString() : null);
  const canSave = changed && !order && !update.isPending;

  const state = timerState(hackathon.timer_starts_at, hackathon.timer_ends_at, now);
  const parts = state.msLeft !== null ? splitDuration(state.msLeft) : null;
  const clock = parts ? `${parts.days > 0 ? `${parts.days}d ` : ""}${pad2(parts.hours)}:${pad2(parts.minutes)}:${pad2(parts.seconds)}` : "";

  const save = () => {
    if (canSave) update.mutate({ timer_starts_at: startIso, timer_ends_at: endIso });
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Event timer</CardTitle>
        <CardDescription>
          Set when the hackathon starts and ends. A countdown then runs by itself on the presentation page and for
          participants. It is only shown; it doesn't open or close anything.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="space-y-1">
          <label htmlFor="timer-start" className="text-sm font-medium">
            Starts (optional)
          </label>
          <div className="flex gap-2">
            <Input id="timer-start" type="datetime-local" value={start} onChange={(e) => setStart(e.target.value)} />
            <Button type="button" variant="outline" size="sm" onClick={() => setStart(toInput(new Date().toISOString()))}>
              Now
            </Button>
          </div>
          {start && <p className="text-xs text-muted-foreground">{longForm(start)}</p>}
        </div>

        <div className="space-y-1">
          <label htmlFor="timer-end" className="text-sm font-medium">
            Ends
          </label>
          <Input id="timer-end" type="datetime-local" value={end} onChange={(e) => setEnd(e.target.value)} />
          {end && <p className="text-xs text-muted-foreground">{longForm(end)}</p>}
          <p className="text-xs text-muted-foreground">Times are in your own timezone and show correctly for everyone.</p>
        </div>

        {order && <p className="text-sm text-destructive">{order}</p>}

        <div className="flex flex-wrap items-center gap-2">
          <Button disabled={!canSave} onClick={save}>
            {update.isPending ? "Saving..." : "Save timer"}
          </Button>
          {(hackathon.timer_starts_at || hackathon.timer_ends_at) && (
            <Button
              variant="outline"
              disabled={update.isPending}
              onClick={() => {
                if (window.confirm("Remove the timer? It disappears from the presentation page and from participants.")) {
                  update.mutate({ timer_starts_at: null, timer_ends_at: null });
                }
              }}
            >
              Clear timer
            </Button>
          )}
        </div>

        {state.phase !== "none" && !changed && (
          <p className="rounded-md bg-muted/50 p-2 text-sm">
            {state.phase === "before" && <>Starts in <strong className="tabular-nums">{clock}</strong></>}
            {state.phase === "running" && (clock ? <>Running: <strong className="tabular-nums">{clock}</strong> left</> : "Under way")}
            {state.phase === "ended" && "The timer has ended."}
          </p>
        )}
        {update.isError && <p className="text-sm text-destructive">{errorMessage(update.error, "Could not save the timer.")}</p>}
      </CardContent>
    </Card>
  );
}
