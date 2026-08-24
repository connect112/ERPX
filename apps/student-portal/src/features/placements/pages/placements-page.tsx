import { format, parseISO } from "date-fns";
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
import { Skeleton } from "@/components/ui/skeleton";
import { Textarea } from "@/components/ui/textarea";
import {
  useApplyToJob,
  useBrowseJobPostings,
  useMyPlacementApplications,
  useWithdrawPlacementApplication,
} from "@/features/placements/api/placements-hooks";
import type { PlacementApplicationStatus } from "@/features/placements/api/placements-api";

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

export function PlacementsPage() {
  const { data: postings, isLoading } = useBrowseJobPostings();
  const { data: applications } = useMyPlacementApplications();
  const withdrawMutation = useWithdrawPlacementApplication();

  const applicationByPosting = new Map((applications ?? []).map((a) => [a.job_posting_id, a]));

  return (
    <div className="space-y-6 p-6">
      <div>
        <h1 className="text-2xl font-semibold">Placements</h1>
        <p className="text-sm text-muted-foreground">Open job postings, and the status of your applications.</p>
      </div>

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
