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
  useApplyToInternship,
  useBrowseInternshipPostings,
  useMyInternshipApplications,
  useMyInternships,
  useWithdrawInternshipApplication,
} from "@/features/internships/api/internships-hooks";
import type { InternshipApplicationStatus } from "@/features/internships/api/internships-api";

const statusVariant: Record<InternshipApplicationStatus, "default" | "success" | "warning" | "destructive" | "secondary"> = {
  applied: "default",
  shortlisted: "warning",
  selected: "success",
  rejected: "destructive",
  withdrawn: "secondary",
};

function ApplyDialog({ postingId, disabled }: { postingId: string; disabled: boolean }) {
  const [open, setOpen] = useState(false);
  const [coverLetter, setCoverLetter] = useState("");
  const applyMutation = useApplyToInternship();

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button className="w-full" disabled={disabled}>
          {disabled ? "Applied" : "Apply"}
        </Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Apply for this internship</DialogTitle>
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

export function InternshipsPage() {
  const { data: postings, isLoading: postingsLoading } = useBrowseInternshipPostings();
  const { data: applications } = useMyInternshipApplications();
  const { data: internships } = useMyInternships();
  const withdrawMutation = useWithdrawInternshipApplication();

  const applicationByPosting = new Map((applications ?? []).map((a) => [a.internship_posting_id, a]));

  return (
    <div className="space-y-6 p-6">
      <div>
        <h1 className="text-2xl font-semibold">Internships</h1>
        <p className="text-sm text-muted-foreground">Open postings, and the status of your applications.</p>
      </div>

      {internships && internships.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Active Internships</CardTitle>
          </CardHeader>
          <CardContent>
            <ul className="divide-y">
              {internships.map((internship) => (
                <li key={internship.id} className="flex items-center justify-between py-2">
                  <span className="text-sm">
                    Started {format(parseISO(internship.start_date), "PP")}
                  </span>
                  <Badge variant={internship.status === "ongoing" ? "success" : "secondary"}>
                    {internship.status}
                  </Badge>
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>
      )}

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Open Postings</CardTitle>
        </CardHeader>
        <CardContent className="p-0">
          {postingsLoading ? (
            <div className="space-y-2 p-6">
              <Skeleton className="h-24 w-full" />
              <Skeleton className="h-24 w-full" />
            </div>
          ) : postings && postings.length > 0 ? (
            <div className="grid gap-4 p-6 sm:grid-cols-2">
              {postings.map((posting) => {
                const application = applicationByPosting.get(posting.id);
                return (
                  <Card key={posting.id}>
                    <CardHeader>
                      <CardTitle className="text-base">{posting.title}</CardTitle>
                      <CardDescription>
                        {posting.location ?? "Remote/TBD"}
                        {posting.duration_months && ` · ${posting.duration_months} months`}
                        {posting.stipend ? ` · ₹${posting.stipend}/mo` : ""}
                      </CardDescription>
                    </CardHeader>
                    <CardContent className="space-y-3">
                      {posting.application_deadline && (
                        <p className="text-sm text-muted-foreground">
                          Apply by {format(parseISO(posting.application_deadline), "PP")}
                        </p>
                      )}
                      {application ? (
                        <div className="flex items-center justify-between">
                          <Badge variant={statusVariant[application.status]}>{application.status}</Badge>
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
                        <ApplyDialog postingId={posting.id} disabled={false} />
                      )}
                    </CardContent>
                  </Card>
                );
              })}
            </div>
          ) : (
            <p className="p-6 text-center text-sm text-muted-foreground">No open postings right now.</p>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
