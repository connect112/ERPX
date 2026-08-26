import { ArrowLeft, ExternalLink, Pencil } from "lucide-react";
import { type ReactNode, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableBody, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import {
  useChangePostingStatus,
  useCompaniesList,
  usePosting,
  usePostingApplications,
} from "@/features/placements/api/placements-hooks";
import { AdzunaAttribution } from "@/features/placements/components/adzuna-attribution";
import { ApplicationRow } from "@/features/placements/components/application-row";
import { PostingFormDialog } from "@/features/placements/components/posting-form-dialog";
import { PostingSourceBadge } from "@/features/placements/components/posting-source-badge";
import { PostingStatusBadge } from "@/features/placements/components/posting-status-badge";
import {
  type PostingStatus,
  jobTypeLabels,
  postingStatusLabels,
  postingStatusValues,
} from "@/features/placements/schemas/posting-schemas";

function DetailRow({ label, value }: { label: string; value: ReactNode }) {
  return (
    <div className="flex items-center justify-between border-b py-3 last:border-0">
      <span className="text-sm text-muted-foreground">{label}</span>
      <span className="text-sm font-medium">{value}</span>
    </div>
  );
}

export function PostingDetailPage() {
  const { postingId } = useParams<{ postingId: string }>();
  const navigate = useNavigate();
  const { data: posting, isLoading } = usePosting(postingId);
  const { data: applications, isLoading: applicationsLoading } = usePostingApplications(postingId);
  const { data: companies } = useCompaniesList({ limit: 200 });
  const changeStatus = useChangePostingStatus(postingId ?? "");
  const [editOpen, setEditOpen] = useState(false);

  if (isLoading || !posting) {
    return (
      <div className="space-y-4 p-8">
        <Skeleton className="h-8 w-64" />
        <Skeleton className="h-64 w-full" />
      </div>
    );
  }

  const company = companies?.items.find((c) => c.id === posting.company_id);

  return (
    <div className="space-y-6 p-8">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Button variant="ghost" size="icon" onClick={() => navigate("/placements/postings")}>
            <ArrowLeft className="h-4 w-4" />
          </Button>
          <div>
            <h1 className="text-2xl font-semibold tracking-tight">{posting.title}</h1>
            <div className="mt-1 flex items-center gap-2">
              <span className="text-xs text-muted-foreground">{company?.name ?? "Unknown company"}</span>
              <PostingStatusBadge status={posting.status} />
              <PostingSourceBadge source={posting.source} />
            </div>
          </div>
        </div>
        <Button variant="outline" onClick={() => setEditOpen(true)}>
          <Pencil className="h-4 w-4" />
          Edit
        </Button>
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        <div className="space-y-6 lg:col-span-2">
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Posting details</CardTitle>
            </CardHeader>
            <CardContent>
              <DetailRow label="Job type" value={jobTypeLabels[posting.job_type]} />
              <DetailRow label="Location" value={posting.location || "—"} />
              <DetailRow
                label="Salary range"
                value={
                  posting.salary_min != null || posting.salary_max != null
                    ? `${posting.salary_min?.toLocaleString() ?? "—"} – ${
                        posting.salary_max?.toLocaleString() ?? "—"
                      }`
                    : "—"
                }
              />
              <DetailRow
                label="Application deadline"
                value={
                  posting.application_deadline
                    ? new Date(posting.application_deadline).toLocaleDateString()
                    : "—"
                }
              />
              {posting.required_skills && (
                <div className="pt-3">
                  <p className="text-sm text-muted-foreground">Required skills</p>
                  <p className="mt-1 whitespace-pre-wrap text-sm">{posting.required_skills}</p>
                </div>
              )}
              {posting.description && (
                <div className="pt-3">
                  <p className="text-sm text-muted-foreground">Description</p>
                  <p className="mt-1 whitespace-pre-wrap text-sm">{posting.description}</p>
                </div>
              )}
              {posting.source_url && (
                <div className="flex items-center justify-between border-t pt-3">
                  <Button asChild variant="outline" size="sm">
                    <a href={posting.source_url} target="_blank" rel="noreferrer">
                      <ExternalLink className="h-4 w-4" />
                      View original listing
                    </a>
                  </Button>
                  {posting.source === "adzuna" && <AdzunaAttribution />}
                </div>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="text-base">Applications</CardTitle>
              <CardDescription>{applications?.length ?? 0} students have applied.</CardDescription>
            </CardHeader>
            <CardContent>
              {applicationsLoading ? (
                <Skeleton className="h-24 w-full" />
              ) : applications && applications.length > 0 ? (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Student</TableHead>
                      <TableHead>Applied</TableHead>
                      <TableHead>Cover letter</TableHead>
                      <TableHead>Status</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {applications.map((application) => (
                      <ApplicationRow
                        key={application.id}
                        postingId={posting.id}
                        application={application}
                      />
                    ))}
                  </TableBody>
                </Table>
              ) : (
                <p className="py-4 text-center text-sm text-muted-foreground">No applications yet.</p>
              )}
            </CardContent>
          </Card>
        </div>

        <div className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Change status</CardTitle>
            </CardHeader>
            <CardContent>
              <Select
                value={posting.status}
                onValueChange={(value) => changeStatus.mutate(value as PostingStatus)}
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {postingStatusValues.map((s) => (
                    <SelectItem key={s} value={s}>
                      {postingStatusLabels[s]}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </CardContent>
          </Card>
        </div>
      </div>

      <PostingFormDialog open={editOpen} onOpenChange={setEditOpen} posting={posting} />
    </div>
  );
}
