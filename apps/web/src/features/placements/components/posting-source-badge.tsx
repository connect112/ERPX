import { Badge } from "@/components/ui/badge";
import { postingSourceLabels } from "@/features/placements/schemas/posting-schemas";

/** Renders nothing for staff-created ("manual") postings — only aggregated
 * postings need a "via X" attribution tag. */
export function PostingSourceBadge({ source }: { source: string }) {
  if (source === "manual") return null;
  const label = postingSourceLabels[source] ?? source;
  return <Badge variant="info">via {label}</Badge>;
}
