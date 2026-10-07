import type { LeaderboardEntry } from "@/features/hackathons/api/hackathons-api";

const MEDAL: Record<number, string> = { 1: "🥇", 2: "🥈", 3: "🥉" };
const RING: Record<number, string> = {
  1: "ring-2 ring-amber-400",
  2: "ring-2 ring-slate-400",
  3: "ring-2 ring-orange-400",
};

/** More teams get more, tighter columns, so everyone fits on the screen without it feeling crowded. */
function columns(count: number): string {
  if (count <= 6) return "sm:grid-cols-2 xl:grid-cols-3";
  if (count <= 12) return "sm:grid-cols-2 lg:grid-cols-3 2xl:grid-cols-4";
  return "sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 2xl:grid-cols-5";
}

/**
 * The teams as a grid of roomy cards (rank, team name, points), used when the bar graph is switched off.
 * Every team is visible at a glance; the top three are picked out.
 */
export function TeamGrid({ entries, compact = false }: { entries: LeaderboardEntry[]; compact?: boolean }) {
  // `compact` is for a card that is only part of the page, where two columns is all that fits.
  return (
    <ul className={`grid grid-cols-1 gap-4 ${compact ? "sm:grid-cols-2" : columns(entries.length)}`} aria-label="Teams">
      {entries.map((entry) => (
        <li
          key={`${entry.rank}-${entry.team_name}`}
          className={`flex flex-col gap-3 rounded-xl border bg-card p-4 shadow-sm ${RING[entry.rank] ?? ""}`}
        >
          <div className="flex items-start justify-between gap-3">
            <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-full bg-muted text-xl font-bold">
              {MEDAL[entry.rank] ?? entry.rank}
            </span>
            <div className="text-right">
              <p className="text-3xl font-bold tabular-nums leading-none">{entry.score}</p>
              <p className="mt-1 text-[10px] uppercase tracking-wide text-muted-foreground">points</p>
            </div>
          </div>
          <div className="min-w-0">
            <p className="line-clamp-2 break-words text-lg font-semibold leading-snug" title={entry.team_name}>
              {entry.team_name}
            </p>
            <p className="mt-0.5 text-xs text-muted-foreground">
              {entry.tasks_scored} task{entry.tasks_scored === 1 ? "" : "s"} scored
            </p>
            {entry.members.length > 0 && (
              <p className="line-clamp-2 text-xs text-muted-foreground">{entry.members.join(", ")}</p>
            )}
          </div>
        </li>
      ))}
    </ul>
  );
}
