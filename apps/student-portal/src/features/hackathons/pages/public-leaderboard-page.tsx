import { Maximize2, Trophy } from "lucide-react";
import { useEffect } from "react";
import { useParams } from "react-router-dom";

import type { PublicLeaderboardEntry } from "@/features/hackathons/api/hackathons-api";
import { usePublicLeaderboard } from "@/features/hackathons/api/hackathons-hooks";

const PODIUM = [
  { ring: "ring-amber-400/70", text: "text-amber-300", bar: "bg-amber-400", label: "1st" },
  { ring: "ring-slate-300/60", text: "text-slate-200", bar: "bg-slate-300", label: "2nd" },
  { ring: "ring-orange-400/60", text: "text-orange-300", bar: "bg-orange-400", label: "3rd" },
];

function ordinal(rank: number): string {
  const lastTwo = rank % 100;
  if (lastTwo >= 11 && lastTwo <= 13) return `${rank}th`;
  return `${rank}${["th", "st", "nd", "rd"][rank % 10 > 3 ? 0 : rank % 10] ?? "th"}`;
}

function PodiumCard({ entry, place, scale }: { entry: PublicLeaderboardEntry; place: number; scale: number }) {
  const style = PODIUM[Math.min(place, 2)];
  return (
    <div
      className={`rounded-2xl bg-white/5 p-6 ring-2 ${style.ring} ${place === 0 ? "md:-translate-y-4 md:py-10" : ""}`}
    >
      <div className="flex items-center justify-between">
        <span className={`text-lg font-semibold ${style.text}`}>{ordinal(entry.rank)}</span>
        <Trophy className={`h-6 w-6 ${style.text}`} aria-hidden />
      </div>
      <p className="mt-3 break-words text-2xl font-bold leading-tight md:text-3xl">{entry.team_name}</p>
      {entry.members.length > 0 && <p className="mt-1 text-sm text-white/60">{entry.members.join(", ")}</p>}
      <p className={`mt-4 text-5xl font-extrabold tabular-nums md:text-6xl ${style.text}`}>{entry.score}</p>
      <p className="text-xs uppercase tracking-wide text-white/50">
        points · {entry.tasks_scored} task{entry.tasks_scored === 1 ? "" : "s"} scored
      </p>
      <div className="mt-4 h-2 overflow-hidden rounded-full bg-white/10">
        <div
          className={`h-full rounded-full transition-all duration-700 ${style.bar}`}
          style={{ width: `${Math.max(3, Math.round((entry.score / scale) * 100))}%` }}
        />
      </div>
    </div>
  );
}

/**
 * A public, full-screen live leaderboard for showing on a projector. Reached through the link the
 * organiser shares (no login); refreshes by itself and only ever shows what the organiser chose to share.
 */
export function PublicLeaderboardPage() {
  const { slug = "" } = useParams<{ slug: string }>();
  const { data, isError, isLoading, dataUpdatedAt } = usePublicLeaderboard(slug);

  useEffect(() => {
    document.title = data ? `${data.title} - live leaderboard` : "Live leaderboard";
    const meta = document.createElement("meta");
    meta.name = "robots";
    meta.content = "noindex";
    document.head.appendChild(meta);
    return () => {
      meta.remove();
    };
  }, [data?.title]); // eslint-disable-line react-hooks/exhaustive-deps

  const entries = data?.entries ?? [];
  const scale = Math.max(data?.max_total ?? 0, ...entries.map((e) => e.score), 1);
  const podium = entries.slice(0, 3);
  const rest = entries.slice(3);

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-950 via-slate-900 to-indigo-950 px-5 py-8 text-white md:px-12">
      <div className="mx-auto max-w-6xl">
        <header className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <p className="flex items-center gap-2 text-sm font-medium uppercase tracking-widest text-emerald-300">
              <span className="relative flex h-2.5 w-2.5">
                <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-400 opacity-75" />
                <span className="relative inline-flex h-2.5 w-2.5 rounded-full bg-emerald-400" />
              </span>
              Live leaderboard
            </p>
            <h1 className="mt-2 text-4xl font-extrabold tracking-tight md:text-6xl">{data?.title ?? " "}</h1>
            {data?.theme && <p className="mt-1 text-lg text-white/60">{data.theme}</p>}
          </div>
          <div className="flex items-center gap-3 text-sm text-white/50">
            {dataUpdatedAt > 0 && <span>Updated {new Date(dataUpdatedAt).toLocaleTimeString()}</span>}
            <button
              type="button"
              className="inline-flex items-center gap-1.5 rounded-md border border-white/20 px-3 py-1.5 text-white/80 hover:bg-white/10"
              onClick={() => {
                if (document.fullscreenElement) void document.exitFullscreen();
                else void document.documentElement.requestFullscreen?.();
              }}
            >
              <Maximize2 className="h-4 w-4" />
              Full screen
            </button>
          </div>
        </header>

        {isLoading ? (
          <p className="mt-24 text-center text-xl text-white/60">Loading…</p>
        ) : isError ? (
          <div className="mt-24 text-center">
            <p className="text-2xl font-semibold">This leaderboard link isn't available</p>
            <p className="mt-2 text-white/60">It may have been turned off or changed. Ask the organisers for the current link.</p>
          </div>
        ) : entries.length === 0 ? (
          <div className="mt-24 text-center">
            <p className="text-2xl font-semibold">No scores yet</p>
            <p className="mt-2 text-white/60">Teams appear here as soon as the first scores are awarded.</p>
          </div>
        ) : (
          <>
            <section className="mt-12 grid gap-5 md:grid-cols-3" aria-label="Top teams">
              {podium.map((entry, index) => (
                <PodiumCard key={`${entry.rank}-${entry.team_name}`} entry={entry} place={index} scale={scale} />
              ))}
            </section>

            {rest.length > 0 && (
              <ol className="mt-10 space-y-3" aria-label="Other teams">
                {rest.map((entry) => (
                  <li
                    key={`${entry.rank}-${entry.team_name}`}
                    className="rounded-xl bg-white/5 px-5 py-4 ring-1 ring-white/10"
                  >
                    <div className="flex items-center gap-4">
                      <span className="w-12 text-2xl font-bold tabular-nums text-white/70">{entry.rank}</span>
                      <div className="min-w-0 flex-1">
                        <p className="truncate text-xl font-semibold">{entry.team_name}</p>
                        {entry.members.length > 0 && (
                          <p className="truncate text-sm text-white/50">{entry.members.join(", ")}</p>
                        )}
                      </div>
                      <span className="text-3xl font-bold tabular-nums">{entry.score}</span>
                    </div>
                    <div className="mt-3 h-1.5 overflow-hidden rounded-full bg-white/10">
                      <div
                        className="h-full rounded-full bg-indigo-400 transition-all duration-700"
                        style={{ width: `${Math.max(2, Math.round((entry.score / scale) * 100))}%` }}
                      />
                    </div>
                  </li>
                ))}
              </ol>
            )}
            {data && data.max_total > 0 && scale === data.max_total && (
              <p className="mt-8 text-center text-sm text-white/40">Bars show progress towards {data.max_total} points.</p>
            )}
          </>
        )}
      </div>
    </div>
  );
}
