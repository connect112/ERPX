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
import { useHackathonsList } from "@/features/hackathons/api/hackathons-hooks";
import { HackathonFormDialog } from "@/features/hackathons/components/hackathon-form-dialog";
import { HackathonStatusBadge } from "@/features/hackathons/components/hackathon-status-badge";
import {
  type HackathonStatus,
  hackathonStatusLabels,
  hackathonStatusValues,
} from "@/features/hackathons/schemas/hackathon-schemas";

const PAGE_SIZE = 20;

export function HackathonsListPage() {
  const navigate = useNavigate();
  const [status, setStatus] = useState<HackathonStatus | "all">("all");
  const [skip, setSkip] = useState(0);
  const [formOpen, setFormOpen] = useState(false);

  const { data, isLoading, isError } = useHackathonsList({
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
          <h1 className="text-2xl font-semibold tracking-tight">Hackathons</h1>
          <p className="mt-1 text-muted-foreground">
            Team-based project competitions with prizes and grading.
          </p>
        </div>
        <Button onClick={() => setFormOpen(true)}>
          <Plus className="h-4 w-4" />
          New Hackathon
        </Button>
      </div>

      <Card>
        <CardContent className="space-y-4 p-6">
          <Select
            value={status}
            onValueChange={(value) => {
              setStatus(value as HackathonStatus | "all");
              setSkip(0);
            }}
          >
            <SelectTrigger className="sm:w-56">
              <SelectValue placeholder="All statuses" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All statuses</SelectItem>
              {hackathonStatusValues.map((s) => (
                <SelectItem key={s} value={s}>
                  {hackathonStatusLabels[s]}
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
              Failed to load hackathons. Please try again.
            </p>
          )}

          {!isLoading && !isError && (data?.items.length ?? 0) === 0 && (
            <p className="py-8 text-center text-sm text-muted-foreground">
              No hackathons found. Create your first hackathon to get started.
            </p>
          )}

          {!isLoading && !isError && (data?.items.length ?? 0) > 0 && (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Code</TableHead>
                  <TableHead>Title</TableHead>
                  <TableHead>Start date</TableHead>
                  <TableHead>Max team size</TableHead>
                  <TableHead>Status</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {data?.items.map((hackathon) => (
                  <TableRow
                    key={hackathon.id}
                    className="cursor-pointer"
                    onClick={() => navigate(`/hackathons/${hackathon.id}`)}
                  >
                    <TableCell className="font-mono text-xs text-muted-foreground">
                      {hackathon.code}
                    </TableCell>
                    <TableCell className="font-medium">{hackathon.title}</TableCell>
                    <TableCell className="text-muted-foreground">
                      {new Date(hackathon.start_date).toLocaleDateString()}
                    </TableCell>
                    <TableCell className="text-muted-foreground">{hackathon.max_team_size}</TableCell>
                    <TableCell>
                      <HackathonStatusBadge status={hackathon.status} />
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}

          {!isLoading && total > PAGE_SIZE && (
            <div className="flex items-center justify-between pt-2">
              <p className="text-sm text-muted-foreground">
                Page {page} of {pageCount} ({total} hackathons)
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

      <HackathonFormDialog open={formOpen} onOpenChange={setFormOpen} />
    </div>
  );
}
