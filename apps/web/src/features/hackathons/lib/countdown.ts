export type TimerPhase = "none" | "before" | "running" | "ended";

export interface TimerState {
  phase: TimerPhase;
  /** Milliseconds until the start (phase "before") or the end (phase "running"); null otherwise. */
  msLeft: number | null;
}

function parse(value: string | null): number | null {
  if (!value) return null;
  const ms = Date.parse(value);
  return Number.isNaN(ms) ? null : ms;
}

/**
 * Where the event's countdown stands at `nowMs`. With a start time it counts down to the start first, then
 * to the end; with only an end time it counts down to the end. Pure, so it is the same everywhere.
 */
export function timerState(startsAt: string | null, endsAt: string | null, nowMs: number): TimerState {
  const start = parse(startsAt);
  const end = parse(endsAt);
  if (start === null && end === null) return { phase: "none", msLeft: null };
  if (start !== null && nowMs < start) return { phase: "before", msLeft: start - nowMs };
  if (end === null) return { phase: "running", msLeft: null };
  if (nowMs < end) return { phase: "running", msLeft: end - nowMs };
  return { phase: "ended", msLeft: null };
}

export interface DurationParts {
  days: number;
  hours: number;
  minutes: number;
  seconds: number;
}

/** A duration in whole seconds, split for a clock face (rounded up so it hits 0 only at the moment). */
export function splitDuration(ms: number): DurationParts {
  const total = Math.max(0, Math.ceil(ms / 1000));
  return {
    days: Math.floor(total / 86400),
    hours: Math.floor((total % 86400) / 3600),
    minutes: Math.floor((total % 3600) / 60),
    seconds: total % 60,
  };
}

export function pad2(n: number): string {
  return String(n).padStart(2, "0");
}
