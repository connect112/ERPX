import { Timer } from "lucide-react";
import { useEffect, useState } from "react";

import { pad2, splitDuration, timerState } from "@/features/hackathons/lib/countdown";

const LABEL = { before: "Starts in", running: "Time left", ended: "Time's up" } as const;

/**
 * The event's countdown, running by itself. `offsetMs` is how far this screen's clock is from the server's,
 * so a projector with the wrong time still shows the right count.
 */
export function EventTimer({
  startsAt,
  endsAt,
  offsetMs = 0,
  size = "compact",
}: {
  startsAt: string | null;
  endsAt: string | null;
  offsetMs?: number;
  size?: "large" | "compact";
}) {
  const [now, setNow] = useState(() => Date.now() + offsetMs);

  useEffect(() => {
    const tick = () => setNow(Date.now() + offsetMs);
    tick();
    const timer = window.setInterval(tick, 1000);
    return () => window.clearInterval(timer);
  }, [offsetMs]);

  const state = timerState(startsAt, endsAt, now);
  if (state.phase === "none") return null;

  if (state.phase === "ended" || state.msLeft === null) {
    const text = state.phase === "ended" ? LABEL.ended : "Under way";
    return size === "large" ? (
      <div className="rounded-xl border bg-card px-6 py-4 text-center" role="timer" aria-label={text}>
        <p className="text-3xl font-bold tracking-tight md:text-5xl">{text}</p>
      </div>
    ) : (
      <span className="inline-flex items-center gap-1.5 rounded-md border px-2.5 py-1 text-sm font-medium" role="timer">
        <Timer className="h-4 w-4" aria-hidden />
        {text}
      </span>
    );
  }

  const parts = splitDuration(state.msLeft);
  const urgent = state.phase === "running" && state.msLeft < 10 * 60 * 1000;

  if (size === "compact") {
    return (
      <span
        className={`inline-flex items-center gap-1.5 rounded-md border px-2.5 py-1 text-sm font-medium tabular-nums ${urgent ? "border-destructive/60 text-destructive" : ""}`}
        role="timer"
        aria-label={`${LABEL[state.phase]} ${parts.days} days ${parts.hours} hours ${parts.minutes} minutes ${parts.seconds} seconds`}
      >
        <Timer className="h-4 w-4" aria-hidden />
        {LABEL[state.phase]} {parts.days > 0 ? `${parts.days}d ` : ""}
        {pad2(parts.hours)}:{pad2(parts.minutes)}:{pad2(parts.seconds)}
      </span>
    );
  }

  const cells: [string, number][] = [
    ["Days", parts.days],
    ["Hours", parts.hours],
    ["Minutes", parts.minutes],
    ["Seconds", parts.seconds],
  ];
  return (
    <div
      className={`rounded-xl border bg-card px-4 py-4 md:px-8 ${urgent ? "border-destructive/60" : ""}`}
      role="timer"
      aria-label={`${LABEL[state.phase]} ${parts.days} days ${parts.hours} hours ${parts.minutes} minutes ${parts.seconds} seconds`}
    >
      <p className={`text-center text-xs font-semibold uppercase tracking-widest ${urgent ? "text-destructive" : "text-muted-foreground"}`}>
        {LABEL[state.phase]}
      </p>
      <div className="mt-2 grid grid-cols-4 gap-2 text-center md:gap-4">
        {cells.map(([label, value]) => (
          <div key={label}>
            <p className={`text-4xl font-extrabold tabular-nums md:text-7xl ${urgent ? "text-destructive" : ""}`}>
              {pad2(value)}
            </p>
            <p className="text-[10px] uppercase tracking-wide text-muted-foreground md:text-xs">{label}</p>
          </div>
        ))}
      </div>
    </div>
  );
}
