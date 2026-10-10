import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { useHashtags } from "@/features/social-media/api/social-media-hooks";
import { formatNumber } from "@/features/social-media/lib/numbers";

const COMPARISON = { higher: "Posts with it reached more", lower: "Posts with it reached fewer", same: "About the same reach" } as const;

/** What the profile's own posts show for each hashtag, kept apart from suggestions and from trends ERPX can't measure. */
export function HashtagPanel() {
  const report = useHashtags();
  const data = report.data;
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Hashtags</CardTitle>
        <CardDescription>{data?.label ?? "Measured from this profile's own posts"}. Hashtags the Studio suggests are suggestions, not measurements.</CardDescription>
      </CardHeader>
      <CardContent className="space-y-3 text-sm">
        {report.isLoading ? (
          <Skeleton className="h-20 w-full" />
        ) : !data ? (
          <p className="text-destructive">Couldn&apos;t load hashtags.</p>
        ) : (
          <>
            <p className="rounded-md bg-muted/40 p-3 text-xs text-muted-foreground">{data.trend.reason}</p>
            {data.items.length === 0 ? (
              <p className="text-muted-foreground">No hashtags found in the posts read from Instagram yet.</p>
            ) : (
              <>
                <p className="text-xs text-muted-foreground">
                  {data.posts_read} post(s) read
                  {data.average_per_post !== null ? `, ${data.average_per_post.toFixed(1)} hashtags per post on average` : ""}
                  {data.too_many ? `, ${data.too_many} over Instagram's limit of 30` : ""}
                  {data.many ? `, ${data.many} with more than 15` : ""}.
                </p>
                {data.repeated_sets.map((s) => (
                  <p key={s.tags.join(",")} className="text-xs text-amber-800">
                    The same set ({s.tags.map((t) => `#${t}`).join(" ")}) was used on {s.posts} posts. Repeating one set can look automatic.
                  </p>
                ))}
                <div className="overflow-x-auto">
                  <table className="w-full min-w-[560px] text-left">
                    <thead className="text-xs text-muted-foreground">
                      <tr>
                        <th className="py-2 pr-3 font-medium">Hashtag</th>
                        <th className="py-2 pr-3 font-medium">Posts</th>
                        <th className="py-2 pr-3 font-medium">Typical reach with it</th>
                        <th className="py-2 pr-3 font-medium">Typical reach without</th>
                        <th className="py-2 pr-3 font-medium">What the posts show</th>
                      </tr>
                    </thead>
                    <tbody>
                      {data.items.slice(0, 30).map((h) => (
                        <tr key={h.tag} className="border-t align-top">
                          <td className="py-2 pr-3 font-medium">
                            #{h.tag} {h.overused && <Badge variant="warning">Used on most recent posts</Badge>}
                          </td>
                          <td className="py-2 pr-3">{h.posts}</td>
                          <td className="py-2 pr-3">
                            {formatNumber(h.median_reach_with)} <span className="text-xs text-muted-foreground">({h.posts_with_reach})</span>
                          </td>
                          <td className="py-2 pr-3">
                            {formatNumber(h.median_reach_without)} <span className="text-xs text-muted-foreground">({h.posts_without_reach})</span>
                          </td>
                          <td className="py-2 pr-3">{h.comparison ? COMPARISON[h.comparison] : <span className="text-xs text-muted-foreground">{h.caution}</span>}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </>
            )}
            <ul className="list-disc space-y-1 pl-4 text-xs text-muted-foreground">
              {data.limitations.map((l) => (
                <li key={l}>{l}</li>
              ))}
            </ul>
          </>
        )}
      </CardContent>
    </Card>
  );
}
