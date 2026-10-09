import type { Breakdown } from "@/features/social-media/api/social-media-api";
import { formatNumber, formatRate } from "@/features/social-media/lib/numbers";

/** Posts grouped by something (format, topic, hook...). The number in brackets is how many posts are behind each figure. */
export function GroupTable({ rows }: { rows: Breakdown[] }) {
  if (rows.length === 0) return <p className="text-sm text-muted-foreground">No posts with readable figures yet.</p>;
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[560px] text-left text-sm">
        <thead className="text-xs text-muted-foreground">
          <tr>
            <th className="py-2 pr-3 font-medium">Group</th>
            <th className="py-2 pr-3 font-medium">Posts</th>
            <th className="py-2 pr-3 font-medium">Typical reach (median)</th>
            <th className="py-2 pr-3 font-medium">Typical saves (median)</th>
            <th className="py-2 pr-3 font-medium">Engagement by reach (pooled)</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((g) => (
            <tr key={g.label} className="border-t align-top">
              <td className="py-2 pr-3 font-medium capitalize">
                {g.label}
                {g.caution && <p className="text-xs font-normal normal-case text-amber-800">{g.caution}</p>}
              </td>
              <td className="py-2 pr-3">{g.posts}</td>
              <td className="py-2 pr-3">
                {formatNumber(g.median_reach)} <span className="text-xs text-muted-foreground">({g.reach_posts})</span>
              </td>
              <td className="py-2 pr-3">
                {formatNumber(g.median_saves)} <span className="text-xs text-muted-foreground">({g.saves_posts})</span>
              </td>
              <td className="py-2 pr-3">
                {formatRate(g.er_reach_pooled)} <span className="text-xs text-muted-foreground">({g.er_reach_posts})</span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
