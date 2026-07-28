import { Plus } from "lucide-react";
import { useState } from "react";
import { useNavigate } from "react-router-dom";

import { Badge, type BadgeProps } from "@/components/ui/badge";
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
import { useJournalsList } from "@/features/accounting/journals/api/journals-hooks";
import { JournalEntryFormDialog } from "@/features/accounting/journals/pages/journal-entry-form-dialog";
import {
  type JournalEntryStatus,
  journalEntryStatusLabels,
  journalEntryStatusValues,
} from "@/features/accounting/journals/schemas/journal-schemas";

const statusVariant: Record<JournalEntryStatus, BadgeProps["variant"]> = {
  draft: "secondary",
  posted: "success",
  reversed: "destructive",
};

export function JournalsListPage() {
  const navigate = useNavigate();
  const [status, setStatus] = useState<JournalEntryStatus | "all">("all");
  const [formOpen, setFormOpen] = useState(false);

  const { data, isLoading, isError } = useJournalsList({
    status: status === "all" ? undefined : status,
    limit: 100,
  });

  return (
    <div className="space-y-6 p-8">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Journal Entries</h1>
          <p className="mt-1 text-muted-foreground">
            Every posting to the general ledger, manual or system-generated.
          </p>
        </div>
        <Button onClick={() => setFormOpen(true)}>
          <Plus className="h-4 w-4" />
          New Entry
        </Button>
      </div>

      <Card>
        <CardContent className="space-y-4 p-6">
          <Select value={status} onValueChange={(v) => setStatus(v as JournalEntryStatus | "all")}>
            <SelectTrigger className="sm:w-48">
              <SelectValue placeholder="All statuses" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All statuses</SelectItem>
              {journalEntryStatusValues.map((s) => (
                <SelectItem key={s} value={s}>
                  {journalEntryStatusLabels[s]}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>

          {isLoading && <Skeleton className="h-32 w-full" />}
          {isError && (
            <p className="py-8 text-center text-sm text-destructive">Failed to load journal entries.</p>
          )}
          {!isLoading && !isError && (data?.items.length ?? 0) === 0 && (
            <p className="py-8 text-center text-sm text-muted-foreground">
              No journal entries yet.
            </p>
          )}
          {!isLoading && !isError && (data?.items.length ?? 0) > 0 && (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Entry #</TableHead>
                  <TableHead>Date</TableHead>
                  <TableHead>Memo</TableHead>
                  <TableHead>Source</TableHead>
                  <TableHead>Status</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {data?.items.map((entry) => (
                  <TableRow
                    key={entry.id}
                    className="cursor-pointer"
                    onClick={() => navigate(`/accounting/journals/${entry.id}`)}
                  >
                    <TableCell className="font-mono text-xs">{entry.entry_number}</TableCell>
                    <TableCell className="text-muted-foreground">
                      {new Date(entry.entry_date).toLocaleDateString()}
                    </TableCell>
                    <TableCell className="text-muted-foreground">{entry.memo || "—"}</TableCell>
                    <TableCell className="text-muted-foreground capitalize">
                      {entry.source_module}
                    </TableCell>
                    <TableCell>
                      <Badge variant={statusVariant[entry.status]}>
                        {journalEntryStatusLabels[entry.status]}
                      </Badge>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      <JournalEntryFormDialog open={formOpen} onOpenChange={setFormOpen} />
    </div>
  );
}
