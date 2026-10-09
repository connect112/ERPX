import { format, formatDistanceToNow, parseISO } from "date-fns";
import { ExternalLink, EyeOff, RefreshCw } from "lucide-react";
import { useEffect, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Textarea } from "@/components/ui/textarea";
import {
  useExternalJobs,
  useJobFeedSettings,
  useRefreshJobFeed,
  useSetExternalJobHidden,
  useUpdateJobFeedSettings,
} from "@/features/placements/api/placements-hooks";
import { JOB_SITE_TOPICS, jobSiteSearchUrl } from "@/features/placements/lib/job-sites";

const PAGE_SIZE = 50;

function errorMessage(error: unknown, fallback: string): string {
  const data = (error as { response?: { data?: { error?: { message?: string; details?: { msg?: string }[] } } } })?.response?.data?.error;
  const detail = Array.isArray(data?.details) ? data?.details[0]?.msg : undefined;
  return (detail ? detail.replace(/^Value error,\s*/, "") : data?.message) ?? fallback;
}

function sourceLabel(name: string, labels: Record<string, string>): string {
  return labels[name]?.split(" (")[0] ?? name;
}

/**
 * Jobs found on outside job sites (through their own feeds / APIs), shown here and on every student's Placements page.
 * Students open the original job page to apply. LinkedIn, Naukri and Indeed don't offer their listings to other
 * software, so for those there are only search links.
 */
export function JobFeedPage() {
  const settings = useJobFeedSettings();
  const update = useUpdateJobFeedSettings();
  const refresh = useRefreshJobFeed();
  const hide = useSetExternalJobHidden();
  const [search, setSearch] = useState("");
  const [source, setSource] = useState("");
  const [showHidden, setShowHidden] = useState(true);
  const [skip, setSkip] = useState(0);
  const [keywords, setKeywords] = useState("");
  const [greenhouse, setGreenhouse] = useState("");
  const [lever, setLever] = useState("");

  const jobs = useExternalJobs({
    q: search || undefined,
    source: source || undefined,
    include_hidden: showHidden,
    skip,
    limit: PAGE_SIZE,
  });

  useEffect(() => {
    if (settings.data) {
      setKeywords(settings.data.keywords.join(", "));
      setGreenhouse((settings.data.boards.greenhouse ?? []).join(", "));
      setLever((settings.data.boards.lever ?? []).join(", "));
    }
  }, [settings.data]);

  const labels = Object.fromEntries((settings.data?.sources ?? []).map((s) => [s.name, s.label]));
  const keywordList = keywords.split(",").map((k) => k.trim()).filter(Boolean);
  const keywordsChanged = settings.data !== undefined && keywordList.join("|") !== settings.data.keywords.join("|");
  const total = jobs.data?.total ?? 0;
  const splitNames = (text: string) => text.split(/[\s,]+/).map((n) => n.trim()).filter(Boolean);
  const boardsChanged =
    settings.data !== undefined &&
    (splitNames(greenhouse).join("|") !== (settings.data.boards.greenhouse ?? []).join("|") ||
      splitNames(lever).join("|") !== (settings.data.boards.lever ?? []).join("|"));
  const refreshing = refresh.isPending || (settings.data?.refreshing ?? false);

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold">Job Feed</h1>
          <p className="text-sm text-muted-foreground">
            Jobs found on outside job sites, shown on every student's Placements page. Students click Apply and go to
            the original job page.
          </p>
        </div>
        <Button disabled={refreshing} onClick={() => refresh.mutate()}>
          <RefreshCw className={`h-4 w-4 ${refreshing ? "animate-spin" : ""}`} />
          {refreshing ? "Checking the job sites..." : "Refresh now"}
        </Button>
      </div>
      {refreshing && (
        <p className="text-sm text-muted-foreground">
          Reading the job sites. This takes a minute or two; new jobs appear below by themselves.
        </p>
      )}
      {refresh.isError && <p className="text-sm text-destructive">{errorMessage(refresh.error, "Could not refresh.")}</p>}

      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Where the jobs come from</CardTitle>
            <CardDescription>
              Each site is asked only a few times a day, as they require. The list refreshes by itself every few hours.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            {settings.isLoading && <Skeleton className="h-24 w-full" />}
            {(settings.data?.sources ?? []).map((s) => (
              <div key={s.name} className="flex items-start gap-3 rounded-md border p-3 text-sm">
                <input
                  type="checkbox"
                  className="mt-1"
                  checked={s.enabled && s.configured}
                  disabled={!s.configured || update.isPending}
                  onChange={(e) => update.mutate({ sources: { [s.name]: e.target.checked } })}
                  aria-label={`Use ${s.label}`}
                />
                <div className="min-w-0 flex-1">
                  <p className="font-medium">{s.label}</p>
                  {!s.configured ? (
                    <p className="text-xs text-amber-700 dark:text-amber-400">
                      Needs an API key on the server (free sign-up on the site); then tick it here.
                    </p>
                  ) : s.last_error ? (
                    <p className="text-xs text-destructive">Last read failed: {s.last_error}</p>
                  ) : s.last_fetch_at ? (
                    <p className="text-xs text-muted-foreground">
                      Read {formatDistanceToNow(parseISO(s.last_fetch_at), { addSuffix: true })}
                      {s.matched !== null && ` - ${s.matched} matching jobs`}
                    </p>
                  ) : (
                    <p className="text-xs text-muted-foreground">Not read yet. Press Refresh now.</p>
                  )}
                </div>
              </div>
            ))}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-base">Which jobs to keep</CardTitle>
            <CardDescription>A job is kept when its title contains one of these words.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            <Textarea rows={4} value={keywords} onChange={(e) => setKeywords(e.target.value)} aria-label="Keywords, separated by commas" />
            <label className="flex items-start gap-2 text-sm">
              <input
                type="checkbox"
                className="mt-0.5"
                checked={settings.data?.india_only ?? true}
                disabled={!settings.data || update.isPending}
                onChange={(e) => update.mutate({ india_only: e.target.checked })}
              />
              <span>Only jobs in India, or remote and open to people in India</span>
            </label>
            <div className="flex items-center gap-2">
              <Button
                variant="outline"
                size="sm"
                disabled={!keywordsChanged || keywordList.length === 0 || update.isPending}
                onClick={() => update.mutate({ keywords: keywordList })}
              >
                Save keywords
              </Button>
              <span className="text-xs text-muted-foreground">Applies from the next refresh.</span>
            </div>
            {update.isError && <p className="text-sm text-destructive">{errorMessage(update.error, "Could not save.")}</p>}
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Company career pages</CardTitle>
          <CardDescription>
            Jobs straight from companies' own career pages (Greenhouse and Lever). Add a company by the name in its
            career page address, e.g. boards.greenhouse.io/<strong>okta</strong> or jobs.lever.co/<strong>paytm</strong>.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="grid gap-3 md:grid-cols-2">
            <div className="space-y-1">
              <label htmlFor="boards-greenhouse" className="text-sm font-medium">Greenhouse companies</label>
              <Textarea id="boards-greenhouse" rows={3} value={greenhouse} onChange={(e) => setGreenhouse(e.target.value)} />
            </div>
            <div className="space-y-1">
              <label htmlFor="boards-lever" className="text-sm font-medium">Lever companies</label>
              <Textarea id="boards-lever" rows={3} value={lever} onChange={(e) => setLever(e.target.value)} />
            </div>
          </div>
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              disabled={!boardsChanged || update.isPending}
              onClick={() => update.mutate({ boards: { greenhouse: splitNames(greenhouse), lever: splitNames(lever) } })}
            >
              Save companies
            </Button>
            <span className="text-xs text-muted-foreground">Names that don't exist are simply skipped. Applies from the next refresh.</span>
          </div>
          {update.isError && <p className="text-sm text-destructive">{errorMessage(update.error, "Could not save.")}</p>}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">LinkedIn, Naukri and Indeed</CardTitle>
          <CardDescription>
            These sites don't allow their listings to be copied into other software, so search links open their own
            pages instead.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-2">
          {JOB_SITE_TOPICS.map((topic) => (
            <div key={topic.label} className="flex flex-wrap items-center gap-2 text-sm">
              <span className="w-52 font-medium">{topic.label}</span>
              {(["linkedin", "naukri", "indeed"] as const).map((site) => (
                <Button key={site} asChild size="sm" variant="outline">
                  <a href={jobSiteSearchUrl(site, topic)} target="_blank" rel="noopener noreferrer">
                    {site === "linkedin" ? "LinkedIn" : site === "naukri" ? "Naukri" : "Indeed"}
                    <ExternalLink className="h-3 w-3" />
                  </a>
                </Button>
              ))}
            </div>
          ))}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Jobs found ({total})</CardTitle>
          <div className="flex flex-wrap items-center gap-2 pt-1">
            <Input
              className="max-w-xs"
              placeholder="Search title, company or place"
              value={search}
              onChange={(e) => {
                setSearch(e.target.value);
                setSkip(0);
              }}
            />
            <select
              className="h-10 rounded-md border bg-background px-3 text-sm"
              value={source}
              onChange={(e) => {
                setSource(e.target.value);
                setSkip(0);
              }}
              aria-label="Source"
            >
              <option value="">All sources</option>
              {(settings.data?.sources ?? []).map((s) => (
                <option key={s.name} value={s.name}>
                  {sourceLabel(s.name, labels)}
                </option>
              ))}
            </select>
            <label className="flex items-center gap-2 text-sm">
              <input type="checkbox" checked={showHidden} onChange={(e) => setShowHidden(e.target.checked)} />
              Show hidden jobs
            </label>
          </div>
        </CardHeader>
        <CardContent className="p-0">
          {jobs.isLoading ? (
            <Skeleton className="m-6 h-32" />
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Job</TableHead>
                  <TableHead>Company</TableHead>
                  <TableHead>Where</TableHead>
                  <TableHead>Source</TableHead>
                  <TableHead>Posted</TableHead>
                  <TableHead className="text-right">Students see it</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {(jobs.data?.items ?? []).map((job) => (
                  <TableRow key={job.id} className={job.hidden ? "opacity-60" : ""}>
                    <TableCell className="max-w-xs">
                      <a href={job.url} target="_blank" rel="noopener noreferrer" className="font-medium text-primary hover:underline">
                        {job.title}
                        <ExternalLink className="ml-1 inline h-3 w-3" />
                      </a>
                      {job.fresher_friendly && <Badge variant="secondary" className="ml-2">Fresher friendly</Badge>}
                    </TableCell>
                    <TableCell>{job.company_name}</TableCell>
                    <TableCell className="text-muted-foreground">{job.remote ? "Remote" : job.location ?? "-"}{job.remote && job.location ? ` (${job.location})` : ""}</TableCell>
                    <TableCell className="text-muted-foreground">{sourceLabel(job.source, labels)}</TableCell>
                    <TableCell className="whitespace-nowrap text-muted-foreground">{job.posted_at ? format(parseISO(job.posted_at), "PP") : "-"}</TableCell>
                    <TableCell className="text-right">
                      <Button
                        size="sm"
                        variant="ghost"
                        disabled={hide.isPending}
                        onClick={() => hide.mutate({ id: job.id, hidden: !job.hidden })}
                      >
                        <EyeOff className="h-4 w-4" />
                        {job.hidden ? "Hidden - show" : "Hide"}
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
                {(jobs.data?.items ?? []).length === 0 && (
                  <TableRow>
                    <TableCell colSpan={6} className="py-8 text-center text-muted-foreground">
                      No jobs yet. Press Refresh now to read the job sites.
                    </TableCell>
                  </TableRow>
                )}
              </TableBody>
            </Table>
          )}
          {(jobs.data?.items ?? []).some((job) => job.source === "adzuna") && (
            <p className="border-t p-3 text-xs text-muted-foreground">
              Jobs by{" "}
              <a href="https://www.adzuna.in" target="_blank" rel="noopener noreferrer" className="font-medium underline">
                Adzuna
              </a>
            </p>
          )}
          {total > PAGE_SIZE && (
            <div className="flex items-center justify-between border-t p-3 text-sm">
              <span className="text-muted-foreground">
                {skip + 1}-{Math.min(skip + PAGE_SIZE, total)} of {total}
              </span>
              <div className="flex gap-2">
                <Button size="sm" variant="outline" disabled={skip === 0} onClick={() => setSkip(Math.max(0, skip - PAGE_SIZE))}>
                  Previous
                </Button>
                <Button size="sm" variant="outline" disabled={skip + PAGE_SIZE >= total} onClick={() => setSkip(skip + PAGE_SIZE)}>
                  Next
                </Button>
              </div>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
