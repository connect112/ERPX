import { AlertTriangle, Info } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { useGrid } from "@/features/social-media/api/social-media-hooks";
import { STATUS_LABEL } from "@/features/social-media/lib/format";

interface Props {
  /** Put this post first (top-left), as it will be when it is posted next. */
  postId?: string;
  compact?: boolean;
}

/**
 * How the next posts will look together on the profile, with an honest list of what is repetitive, dense or abrupt.
 * Posts already on the live Instagram profile aren't included until the account is connected, and the preview says so.
 */
export function GridPreview({ postId, compact = false }: Props) {
  const grid = useGrid(postId);

  if (grid.isLoading) return <Skeleton className="h-48 w-full" />;
  if (grid.isError || !grid.data) return <p className="text-sm text-destructive">Couldn&apos;t build the grid preview.</p>;
  const { tiles, findings, verdict, missing, note } = grid.data;
  const cells = Array.from({ length: 9 }, (_, i) => tiles[i] ?? null);
  const flagged = new Set(findings.filter((f) => f.severity === "warning").flatMap((f) => f.tiles));

  return (
    <div className="space-y-3">
      <div className={compact ? "mx-auto grid max-w-xs grid-cols-3 gap-1" : "mx-auto grid max-w-md grid-cols-3 gap-1.5"}>
        {cells.map((tile, i) =>
          tile ? (
            <div key={tile.post_id} className={`relative aspect-[4/5] overflow-hidden rounded-sm border ${flagged.has(i) ? "border-amber-500" : "border-border"} ${tile.is_focus ? "ring-2 ring-primary" : ""}`}>
              {tile.url ? (
                <img src={tile.url} alt={`Artwork for ${tile.title}`} className="h-full w-full object-cover" loading="lazy" />
              ) : (
                <div className="flex h-full items-center justify-center bg-muted p-1 text-center text-[10px] text-muted-foreground">No preview</div>
              )}
              {!compact && (
                <span className="absolute inset-x-0 bottom-0 truncate bg-black/60 px-1 py-0.5 text-[10px] text-white">
                  {tile.is_focus ? "This post · " : ""}
                  {STATUS_LABEL[tile.status]}
                </span>
              )}
              {tile.synthetic_background && <span className="absolute left-1 top-1 rounded bg-black/70 px-1 text-[9px] text-white">AI background</span>}
            </div>
          ) : (
            <div key={`empty-${i}`} className="flex aspect-[4/5] items-center justify-center rounded-sm border border-dashed text-[10px] text-muted-foreground">
              No post
            </div>
          ),
        )}
      </div>
      <div className="flex flex-wrap items-center gap-2 text-sm">
        {verdict === "balanced" && <Badge variant="success">Looks balanced</Badge>}
        {verdict === "review" && <Badge variant="warning">Worth a look</Badge>}
        {verdict === "not_enough" && <Badge variant="secondary">Not enough designed posts to judge</Badge>}
        {missing > 0 && <span className="text-xs text-muted-foreground">{missing} of 9 spaces have no designed post.</span>}
      </div>
      {findings.length > 0 && (
        <ul className="space-y-1.5 text-sm">
          {findings.map((f, i) => (
            <li key={`${f.code}-${i}`} className="flex items-start gap-2">
              {f.severity === "warning" ? (
                <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-amber-600" aria-hidden />
              ) : (
                <Info className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground" aria-hidden />
              )}
              <span>
                {f.message}
                {f.tiles.length > 0 && <span className="text-muted-foreground"> (posts {f.tiles.map((t) => t + 1).join(", ")})</span>}
              </span>
            </li>
          ))}
        </ul>
      )}
      <p className="text-xs text-muted-foreground">{note}</p>
    </div>
  );
}
