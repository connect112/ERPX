import { ExternalLink, RefreshCw, Search } from "lucide-react";
import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { useMyRoles } from "@/features/auth/api/authorization-hooks";
import type { RefreshResult, ResearchItem } from "@/features/social-media/api/social-media-api";
import {
  useDismissResearch,
  useLookUpCve,
  useRefreshResearch,
  useResearch,
  useSocialSettings,
} from "@/features/social-media/api/social-media-hooks";
import { errorMessage, formatInZone } from "@/features/social-media/lib/format";

const NATIVE_SELECT = "h-10 rounded-md border border-input bg-background px-3 text-sm focus:outline-none focus:ring-2 focus:ring-ring";
const SEVERITY_VARIANT: Record<string, "destructive" | "warning" | "info" | "secondary"> = {
  critical: "destructive",
  high: "warning",
  medium: "info",
  low: "secondary",
};

interface Props {
  onDraftFrom: (itemId: string) => void;
}

function ItemCard({ item, timeZone, canManage, onDraftFrom }: { item: ResearchItem; timeZone: string; canManage: boolean; onDraftFrom: (id: string) => void }) {
  const dismiss = useDismissResearch();
  const kev = item.facts.kev === true;
  return (
    <Card>
      <CardContent className="space-y-2 p-4">
        <div className="flex flex-wrap items-start justify-between gap-2">
          <p className="font-medium">{item.title}</p>
          <div className="flex flex-wrap gap-1.5">
            <Badge variant="outline">{item.source === "cisa_kev" ? "CISA known exploited" : "CISA advisory"}</Badge>
            {kev && <Badge variant="destructive">Exploited (CISA KEV)</Badge>}
            {item.severity && <Badge variant={SEVERITY_VARIANT[item.severity] ?? "secondary"}>{item.severity}</Badge>}
            {item.status === "used" && <Badge variant="secondary">Used in a draft</Badge>}
          </div>
        </div>
        {item.summary && <p className="line-clamp-3 text-sm text-muted-foreground">{item.summary}</p>}
        <p className="text-xs text-muted-foreground">
          {item.published_at ? `Published ${formatInZone(item.published_at, timeZone)} · ` : "No publication date · "}
          retrieved {formatInZone(item.retrieved_at, timeZone)}
          {item.cve_ids.length > 0 ? ` · ${item.cve_ids.join(", ")}` : ""}
        </p>
        {item.flags.length > 0 && (
          <p className="text-xs text-amber-700">
            Warning: this text contains wording that looks like an instruction to an AI. It is only ever used as data.
          </p>
        )}
        <div className="flex flex-wrap gap-2">
          <a
            className="inline-flex h-9 items-center gap-1 rounded-md border px-3 text-sm hover:bg-accent"
            href={item.url}
            target="_blank"
            rel="noreferrer noopener"
          >
            <ExternalLink className="h-3.5 w-3.5" /> Open source
          </a>
          {canManage && (
            <>
              <Button size="sm" onClick={() => onDraftFrom(item.id)}>
                Draft a post from this
              </Button>
              <Button size="sm" variant="outline" disabled={dismiss.isPending} onClick={() => dismiss.mutate(item.id)}>
                Dismiss
              </Button>
            </>
          )}
        </div>
      </CardContent>
    </Card>
  );
}

/** What CISA has published recently, with where and when it was retrieved. Nothing here is made up: if a source can't be reached, it says so. */
export function ResearchTab({ onDraftFrom }: Props) {
  const [source, setSource] = useState("");
  const [search, setSearch] = useState("");
  const [cve, setCve] = useState("");
  const [results, setResults] = useState<RefreshResult[] | null>(null);
  const [lookup, setLookup] = useState<{ ok: boolean; text: string } | null>(null);
  const research = useResearch({ source: source || undefined, q: search || undefined, limit: 50 });
  const settings = useSocialSettings();
  const refresh = useRefreshResearch();
  const look = useLookUpCve();
  const me = useMyRoles();
  const canManage = (me.data?.is_superuser ?? false) || (me.data?.effective_permissions ?? []).includes("social_media.manage");
  const timeZone = settings.data?.timezone ?? "Asia/Kolkata";

  function lookUp() {
    setLookup(null);
    look.mutate(cve.trim(), {
      onSuccess: (item) => {
        const facts = item.facts as { cvss_score?: number; kev?: boolean };
        setLookup({
          ok: true,
          text: `${item.external_id}: ${facts.cvss_score != null ? `CVSS ${facts.cvss_score} (${item.severity ?? "n/a"})` : "no CVSS score listed"}; ${facts.kev ? "in" : "not in"} CISA's Known Exploited Vulnerabilities catalogue. Retrieved ${formatInZone(item.retrieved_at, timeZone)}.`,
        });
      },
      onError: (e) => setLookup({ ok: false, text: errorMessage(e, "Couldn't look that up.") }),
    });
  }

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader>
          <CardTitle>Sources</CardTitle>
          <CardDescription>Official sources only: CISA advisories and CISA&apos;s Known Exploited Vulnerabilities list, plus NVD for CVE facts.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-3 text-sm">
          {research.data &&
            Object.entries(research.data.sources).map(([key, info]) => (
              <div key={key} className="flex flex-wrap items-center gap-2">
                <span className="font-medium">{info.label}</span>
                {info.last_fetch_at ? (
                  <span className="text-muted-foreground">last read {formatInZone(info.last_fetch_at, timeZone)}</span>
                ) : (
                  <span className="text-muted-foreground">not read yet</span>
                )}
                {info.ok === false && <Badge variant="destructive">Couldn&apos;t be read: {info.error}</Badge>}
                {info.ok === true && <Badge variant="success">OK</Badge>}
              </div>
            ))}
          <div className="flex flex-wrap items-center gap-2">
            {canManage && (
              <Button onClick={() => refresh.mutate(true, { onSuccess: setResults })} disabled={refresh.isPending}>
                <RefreshCw className={`mr-1 h-4 w-4 ${refresh.isPending ? "animate-spin" : ""}`} />
                {refresh.isPending ? "Reading sources..." : "Read the sources now"}
              </Button>
            )}
            {refresh.isError && <span className="text-destructive">{errorMessage(refresh.error, "Couldn't read the sources.")}</span>}
          </div>
          {results && (
            <ul className="space-y-1 text-xs">
              {results.map((r) => (
                <li key={r.source} className={r.ok ? "" : "text-destructive"}>
                  {r.label}: {r.ok ? `${r.new} new, ${r.count} recent` : `not read (${r.error})`}
                </li>
              ))}
            </ul>
          )}
        </CardContent>
      </Card>

      {canManage && (
        <Card>
          <CardHeader>
            <CardTitle>Look up a CVE</CardTitle>
            <CardDescription>Checks the identifier in the National Vulnerability Database: whether it exists, its score, and whether it is known to be exploited.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-2">
            <div className="flex flex-wrap gap-2">
              <Input className="max-w-xs" placeholder="CVE-2021-44228" aria-label="CVE identifier" value={cve} onChange={(e) => setCve(e.target.value)} />
              <Button onClick={lookUp} disabled={look.isPending || !/^cve-\d{4}-\d{4,7}$/i.test(cve.trim())}>
                <Search className="mr-1 h-4 w-4" /> {look.isPending ? "Looking up..." : "Look up"}
              </Button>
            </div>
            {lookup && <p role="status" className={lookup.ok ? "text-sm" : "text-sm text-destructive"}>{lookup.text}</p>}
          </CardContent>
        </Card>
      )}

      <div className="flex flex-wrap items-center gap-2">
        <select aria-label="Filter by source" className={NATIVE_SELECT} value={source} onChange={(e) => setSource(e.target.value)}>
          <option value="">All sources</option>
          <option value="cisa_kev">Known exploited (CISA KEV)</option>
          <option value="cisa_advisory">CISA advisories</option>
        </select>
        <Input className="max-w-xs" placeholder="Search titles" value={search} onChange={(e) => setSearch(e.target.value)} />
      </div>

      {research.isLoading ? (
        <Skeleton className="h-32 w-full" />
      ) : research.isError ? (
        <p className="text-sm text-destructive">Couldn&apos;t load the research.</p>
      ) : research.data && research.data.items.length === 0 ? (
        <Card>
          <CardContent className="py-10 text-center text-sm text-muted-foreground">
            Nothing here yet. Use &quot;Read the sources now&quot; to pull the latest advisories.
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-3">
          {research.data?.items.map((item) => (
            <ItemCard key={item.id} item={item} timeZone={timeZone} canManage={canManage} onDraftFrom={onDraftFrom} />
          ))}
        </div>
      )}
    </div>
  );
}
