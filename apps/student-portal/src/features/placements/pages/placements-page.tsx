import { format, formatDistanceToNow, parseISO } from "date-fns";
import { ExternalLink } from "lucide-react";
import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Textarea } from "@/components/ui/textarea";
import {
  useApplyToJob,
  useBrowseJobPostings,
  useExternalJobs,
  useMyPlacementApplications,
  useWithdrawPlacementApplication,
} from "@/features/placements/api/placements-hooks";
import type { PlacementApplicationStatus } from "@/features/placements/api/placements-api";
import { EXPERIENCE_FILTERS, experienceLabel } from "@/features/placements/lib/experience";
import { JOB_SITE_TOPICS, jobSiteSearchUrl } from "@/features/placements/lib/job-sites";

const statusVariant: Record<
  PlacementApplicationStatus,
  "default" | "success" | "warning" | "destructive" | "secondary" | "info"
> = {
  applied: "default",
  shortlisted: "warning",
  interview_scheduled: "info",
  offered: "success",
  rejected: "destructive",
  withdrawn: "secondary",
};

const jobTypeLabel: Record<string, string> = {
  full_time: "Full-time",
  part_time: "Part-time",
  internship: "Internship",
  contract: "Contract",
};

function ApplyDialog({ postingId }: { postingId: string }) {
  const [open, setOpen] = useState(false);
  const [coverLetter, setCoverLetter] = useState("");
  const applyMutation = useApplyToJob();

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button className="w-full">Apply</Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Apply for this role</DialogTitle>
          <DialogDescription>A cover letter is optional but recommended.</DialogDescription>
        </DialogHeader>
        <Textarea
          placeholder="Why are you a good fit for this role? (optional)"
          value={coverLetter}
          onChange={(e) => setCoverLetter(e.target.value)}
          rows={5}
        />
        <DialogFooter>
          <Button
            disabled={applyMutation.isPending}
            onClick={() =>
              applyMutation.mutate(
                { postingId, coverLetter: coverLetter.trim() || undefined },
                { onSuccess: () => setOpen(false) }
              )
            }
          >
            {applyMutation.isPending ? "Submitting…" : "Submit application"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function CompanyOpenings() {
  const { data: postings, isLoading } = useBrowseJobPostings();
  const { data: applications } = useMyPlacementApplications();
  const withdrawMutation = useWithdrawPlacementApplication();

  const applicationByPosting = new Map((applications ?? []).map((a) => [a.job_posting_id, a]));

  return (
    <div className="space-y-6">
      {isLoading ? (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          <Skeleton className="h-40 w-full" />
          <Skeleton className="h-40 w-full" />
        </div>
      ) : postings && postings.length > 0 ? (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {postings.map((posting) => {
            const application = applicationByPosting.get(posting.id);
            return (
              <Card key={posting.id}>
                <CardHeader>
                  <div className="flex items-start justify-between gap-2">
                    <CardTitle className="text-base">{posting.title}</CardTitle>
                    <Badge variant="secondary">{jobTypeLabel[posting.job_type] ?? posting.job_type}</Badge>
                  </div>
                  <CardDescription>{posting.location ?? "Remote/TBD"}</CardDescription>
                </CardHeader>
                <CardContent className="space-y-3">
                  {(posting.salary_min || posting.salary_max) && (
                    <p className="text-sm text-muted-foreground">
                      ₹{posting.salary_min ?? "?"} – ₹{posting.salary_max ?? "?"}
                    </p>
                  )}
                  {posting.application_deadline && (
                    <p className="text-sm text-muted-foreground">
                      Apply by {format(parseISO(posting.application_deadline), "PP")}
                    </p>
                  )}
                  {application ? (
                    <div className="flex items-center justify-between">
                      <Badge variant={statusVariant[application.status]}>
                        {application.status.replace("_", " ")}
                      </Badge>
                      {application.status === "applied" && (
                        <Button
                          size="sm"
                          variant="outline"
                          disabled={withdrawMutation.isPending}
                          onClick={() => withdrawMutation.mutate(application.id)}
                        >
                          Withdraw
                        </Button>
                      )}
                    </div>
                  ) : (
                    <ApplyDialog postingId={posting.id} />
                  )}
                </CardContent>
              </Card>
            );
          })}
        </div>
      ) : (
        <p className="py-6 text-center text-sm text-muted-foreground">No open postings right now.</p>
      )}
    </div>
  );
}

const sourceName: Record<string, string> = {
  remotive: "Remotive",
  arbeitnow: "Arbeitnow",
  adzuna: "Adzuna",
  jooble: "Jooble",
};

const PAGE_SIZE = 24;

/** Jobs found on outside job sites. Apply opens the original job page in a new tab. */
function JobsFromJobSites() {
  const [search, setSearch] = useState("");
  const [skip, setSkip] = useState(0);
  const [experience, setExperience] = useState("");
  const { data, isLoading, isError } = useExternalJobs({
    q: search.trim() || undefined,
    experience: experience || undefined,
    skip,
    limit: PAGE_SIZE,
  });
  const total = data?.total ?? 0;

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center gap-4">
        <Input
          className="max-w-md"
          placeholder="Search by job title, company or place"
          value={search}
          onChange={(e) => {
            setSearch(e.target.value);
            setSkip(0);
          }}
        />
        <select
          className="h-10 rounded-md border bg-background px-3 text-sm"
          value={experience}
          onChange={(e) => {
            setExperience(e.target.value);
            setSkip(0);
          }}
          aria-label="Experience"
        >
          <option value="">Any experience</option>
          {EXPERIENCE_FILTERS.map((f) => (
            <option key={f.value} value={f.value}>
              {f.label}
            </option>
          ))}
        </select>
        {data && (
          <span className="text-sm text-muted-foreground">
            {data.total} job{data.total === 1 ? "" : "s"}
          </span>
        )}
      </div>

      {isLoading ? (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          <Skeleton className="h-48 w-full" />
          <Skeleton className="h-48 w-full" />
          <Skeleton className="h-48 w-full" />
        </div>
      ) : isError ? (
        <p className="py-6 text-center text-sm text-destructive">Could not load jobs. Please try again.</p>
      ) : (data?.items ?? []).length > 0 ? (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {(data?.items ?? []).map((job) => (
            <Card key={job.id} className="flex flex-col">
              <CardHeader>
                <div className="flex items-start justify-between gap-2">
                  <CardTitle className="text-base leading-snug">{job.title}</CardTitle>
                  {job.fresher_friendly && <Badge variant="success">Fresher friendly</Badge>}
                </div>
                <CardDescription>
                  {job.company_name} · {job.remote ? "Remote" : job.location ?? "Location not given"}
                  {job.remote && job.location ? ` (${job.location})` : ""}
                </CardDescription>
              </CardHeader>
              <CardContent className="flex flex-1 flex-col justify-between gap-3">
                <div className="space-y-2">
                  {job.summary && <p className="line-clamp-3 text-sm text-muted-foreground">{job.summary}</p>}
                  <p className="text-sm">
                    <span className="text-muted-foreground">Experience: </span>
                    {experienceLabel(job)}
                  </p>
                  {job.salary_text && <p className="text-sm">{job.salary_text}</p>}
                  <p className="text-xs text-muted-foreground">
                    {job.posted_at ? `Posted ${formatDistanceToNow(parseISO(job.posted_at), { addSuffix: true })} · ` : ""}
                    via {sourceName[job.source] ?? job.source}
                  </p>
                </div>
                <Button asChild className="w-full">
                  <a href={job.url} target="_blank" rel="noopener noreferrer">
                    Apply on the job site
                    <ExternalLink className="h-4 w-4" />
                  </a>
                </Button>
              </CardContent>
            </Card>
          ))}
        </div>
      ) : (
        <p className="py-6 text-center text-sm text-muted-foreground">
          {search.trim() ? "No jobs match your search." : "No jobs have been found yet. Check back soon."}
        </p>
      )}

      {total > PAGE_SIZE && (
        <div className="flex items-center justify-between text-sm">
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

      {(data?.items ?? []).some((job) => job.source === "adzuna") && (
        <p className="text-xs text-muted-foreground">
          Jobs by{" "}
          <a href="https://www.adzuna.in" target="_blank" rel="noopener noreferrer" className="font-medium underline">
            Adzuna
          </a>
        </p>
      )}

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Search on LinkedIn, Naukri and Indeed</CardTitle>
          <CardDescription>These open each site's own search results in a new tab.</CardDescription>
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
    </div>
  );
}

export function PlacementsPage() {
  return (
    <div className="space-y-6 p-6">
      <div>
        <h1 className="text-2xl font-semibold">Placements</h1>
        <p className="text-sm text-muted-foreground">
          Jobs from job sites around the web, openings from our hiring partners, and the status of your applications.
        </p>
      </div>
      <Tabs defaultValue="jobs">
        <TabsList>
          <TabsTrigger value="jobs">Jobs from job sites</TabsTrigger>
          <TabsTrigger value="partners">Our hiring partners</TabsTrigger>
        </TabsList>
        <TabsContent value="jobs">
          <JobsFromJobSites />
        </TabsContent>
        <TabsContent value="partners">
          <CompanyOpenings />
        </TabsContent>
      </Tabs>
    </div>
  );
}
