import { Plus } from "lucide-react";
import { useState } from "react";
import { useNavigate } from "react-router-dom";

import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { usePostingsList } from "@/features/placements/api/placements-hooks";
import { PostingFormDialog } from "@/features/placements/components/posting-form-dialog";
import { PostingStatusBadge } from "@/features/placements/components/posting-status-badge";
import {
  type PostingStatus,
  jobTypeLabels,
  postingStatusLabels,
  postingStatusValues,
} from "@/features/placements/schemas/posting-schemas";

const PAGE_SIZE = 20;

export function PostingsListPage() {
  const navigate = useNavigate();
  const [status, setStatus] = useState<PostingStatus | "all">("all");
  const [skip, setSkip] = useState(0);
  const [formOpen, setFormOpen] = useState(false);

  const { data, isLoading, isError } = usePostingsList({
    status: status === "all" ? undefined : status,
    skip,
    limit: PAGE_SIZE,
  });

  const total = data?.total ?? 0;
  const page = Math.floor(skip / PAGE_SIZE) + 1;
  const pageCount = Math.max(1, Math.ceil(total / PAGE_SIZE));

  return (
    <div className="space-y-6 p-8">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Job Postings</h1>
          <p className="mt-1 text-muted-foreground">
            Open roles that students can browse and apply to from the student portal.
          </p>
        </div>
        <Button onClick={() => setFormOpen(true)}>
          <Plus className="h-4 w-4" />
          New Posting
        </Button>
      </div>

      <Card>
        <CardContent className="space-y-4 p-6">
          <Select
            value={status}
            onValueChange={(value) => {
              setStatus(value as PostingStatus | "all");
              setSkip(0);
            }}
          >
            <SelectTrigger className="sm:w-56">
              <SelectValue placeholder="All statuses" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All statuses</SelectItem>
              {postingStatusValues.map((s) => (
                <SelectItem key={s} value={s}>
                  {postingStatusLabels[s]}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>

          {isLoading && (
            <div className="space-y-2">
              {Array.from({ length: 5 }).map((_, i) => (
                <Skeleton key={i} className="h-12 w-full" />
              ))}
            </div>
          )}

          {isError && (
            <p className="py-8 text-center text-sm text-destructive">
              Failed to load job postings. Please try again.
            </p>
          )}

          {!isLoading && !isError && (data?.items.length ?? 0) === 0 && (
            <p className="py-8 text-center text-sm text-muted-foreground">
              No job postings found. Create your first posting to get started.
            </p>
          )}

          {!isLoading && !isError && (data?.items.length ?? 0) > 0 && (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Title</TableHead>
                  <TableHead>Job type</TableHead>
                  <TableHead>Location</TableHead>
                  <TableHead>Status</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {data?.items.map((posting) => (
                  <TableRow
                    key={posting.id}
                    className="cursor-pointer"
                    onClick={() => navigate(`/placements/postings/${posting.id}`)}
                  >
                    <TableCell className="font-medium">{posting.title}</TableCell>
                    <TableCell className="text-muted-foreground">
                      {jobTypeLabels[posting.job_type]}
                    </TableCell>
                    <TableCell className="text-muted-foreground">{posting.location || "—"}</TableCell>
                    <TableCell>
                      <PostingStatusBadge status={posting.status} />
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}

          {!isLoading && total > PAGE_SIZE && (
            <div className="flex items-center justify-between pt-2">
              <p className="text-sm text-muted-foreground">
                Page {page} of {pageCount} ({total} postings)
              </p>
              <div className="flex gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  disabled={skip === 0}
                  onClick={() => setSkip(Math.max(0, skip - PAGE_SIZE))}
                >
                  Previous
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  disabled={skip + PAGE_SIZE >= total}
                  onClick={() => setSkip(skip + PAGE_SIZE)}
                >
                  Next
                </Button>
              </div>
            </div>
          )}
        </CardContent>
      </Card>

      <PostingFormDialog open={formOpen} onOpenChange={setFormOpen} />
    </div>
  );
}
