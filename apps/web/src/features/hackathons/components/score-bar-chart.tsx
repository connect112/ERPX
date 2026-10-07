import type { LeaderboardEntry } from "@/features/hackathons/api/hackathons-api";
import { barPercent, topScore } from "@/features/hackathons/lib/bar-scale";

const PODIUM_COLORS: Record<number, string> = {
  1: "bg-amber-400",
  2: "bg-slate-400",
  3: "bg-orange-400",
};

/**
 * Bar graph of team totals. The leading team's score fills the chart and every other bar is its
 * share of that, so a team that pulls ahead makes everyone else's bar shorter.
 */
export function ScoreBarChart({ entries }: { entries: LeaderboardEntry[] }) {
  const shown = entries.slice(0, 12);
  const scale = topScore(shown.map((e) => e.score));
  const ticks = [scale, Math.round(scale / 2), 0];

  return (
    <figure className="space-y-2" aria-label="Bar graph of team scores">
      <div className="flex gap-2">
        <div className="flex h-52 w-10 shrink-0 flex-col justify-between text-right text-[11px] tabular-nums text-muted-foreground">
          {ticks.map((tick) => (
            <span key={tick}>{tick}</span>
          ))}
        </div>
        <div className="relative min-w-0 flex-1 overflow-x-auto">
          <div className="pointer-events-none absolute inset-x-0 top-0 h-52">
            <div className="absolute inset-x-0 top-0 border-t border-dashed border-border" />
            <div className="absolute inset-x-0 top-1/2 border-t border-dashed border-border" />
          </div>
          <div className="relative flex h-52 items-end gap-3 border-b px-1" style={{ minWidth: `${shown.length * 4.5}rem` }}>
            {shown.map((entry) => {
              const percent = barPercent(entry.score, scale);
              return (
                <div key={`${entry.rank}-${entry.team_name}`} className="flex h-full w-16 flex-col items-center justify-end">
                  <span className="mb-1 text-xs font-semibold tabular-nums">{entry.score}</span>
                  <div
                    className={`w-full rounded-t-md transition-all duration-500 ${PODIUM_COLORS[entry.rank] ?? "bg-primary"}`}
                    style={{ height: `${percent}%` }}
                    role="img"
                    aria-label={`${entry.team_name}: ${entry.score} points, rank ${entry.rank}`}
                  />
                </div>
              );
            })}
          </div>
          <div className="flex gap-3 px-1 pt-1.5" style={{ minWidth: `${shown.length * 4.5}rem` }}>
            {shown.map((entry) => (
              <div key={`${entry.rank}-${entry.team_name}-label`} className="w-16 text-center">
                <p className="truncate text-[11px] font-medium" title={entry.team_name}>
                  {entry.team_name}
                </p>
                <p className="text-[10px] text-muted-foreground">#{entry.rank}</p>
              </div>
            ))}
          </div>
        </div>
      </div>
      <figcaption className="text-xs text-muted-foreground">
        Total marks per team, scaled to the top score
        {entries.length > shown.length ? `, top ${shown.length} teams shown` : ""}.
      </figcaption>
    </figure>
  );
}
