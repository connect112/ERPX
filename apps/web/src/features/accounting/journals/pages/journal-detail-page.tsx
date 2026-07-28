import { ArrowLeft } from "lucide-react";
import { useNavigate, useParams } from "react-router-dom";

import { Badge, type BadgeProps } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { useAccountsList } from "@/features/accounting/ledger/api/accounts-hooks";
import {
  useJournalEntry,
  usePostJournalEntry,
  useReverseJournalEntry,
} from "@/features/accounting/journals/api/journals-hooks";
import {
  type JournalEntryStatus,
  journalEntryStatusLabels,
  journalSourceModuleLabels,
} from "@/features/accounting/journals/schemas/journal-schemas";

const statusVariant: Record<JournalEntryStatus, BadgeProps["variant"]> = {
  draft: "secondary",
  posted: "success",
  reversed: "destructive",
};

export function JournalDetailPage() {
  const { entryId } = useParams<{ entryId: string }>();
  const navigate = useNavigate();
  const { data: entry, isLoading } = useJournalEntry(entryId);
  const { data: accounts } = useAccountsList({ limit: 500 });
  const postEntry = usePostJournalEntry();
  const reverseEntry = useReverseJournalEntry();

  if (isLoading || !entry) {
    return (
      <div className="space-y-4 p-8">
        <Skeleton className="h-8 w-64" />
        <Skeleton className="h-64 w-full" />
      </div>
    );
  }

  const accountLabel = (id: string) => {
    const account = accounts?.items.find((a) => a.id === id);
    return account ? `${account.code} — ${account.name}` : id;
  };

  const totalDebit = entry.lines.reduce((sum, l) => sum + l.debit, 0);
  const totalCredit = entry.lines.reduce((sum, l) => sum + l.credit, 0);

  return (
    <div className="space-y-6 p-8">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Button variant="ghost" size="icon" onClick={() => navigate("/accounting/journals")}>
            <ArrowLeft className="h-4 w-4" />
          </Button>
          <div>
            <h1 className="text-2xl font-semibold tracking-tight">{entry.entry_number}</h1>
            <div className="mt-1 flex items-center gap-2">
              <Badge variant={statusVariant[entry.status]}>
                {journalEntryStatusLabels[entry.status]}
              </Badge>
              <Badge variant="outline">{journalSourceModuleLabels[entry.source_module]}</Badge>
            </div>
          </div>
        </div>
        <div className="flex gap-2">
          {entry.status === "draft" && (
            <Button onClick={() => postEntry.mutate(entry.id)} disabled={postEntry.isPending}>
              {postEntry.isPending ? "Posting..." : "Post entry"}
            </Button>
          )}
          {entry.status === "posted" && (
            <Button
              variant="destructive"
              onClick={() => reverseEntry.mutate(entry.id)}
              disabled={reverseEntry.isPending}
            >
              {reverseEntry.isPending ? "Reversing..." : "Reverse entry"}
            </Button>
          )}
        </div>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Entry details</CardTitle>
        </CardHeader>
        <CardContent className="space-y-1 text-sm">
          <p>
            <span className="text-muted-foreground">Date:</span>{" "}
            {new Date(entry.entry_date).toLocaleString()}
          </p>
          {entry.memo && (
            <p>
              <span className="text-muted-foreground">Memo:</span> {entry.memo}
            </p>
          )}
          {entry.posted_at && (
            <p>
              <span className="text-muted-foreground">Posted at:</span>{" "}
              {new Date(entry.posted_at).toLocaleString()}
            </p>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Lines</CardTitle>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Account</TableHead>
                <TableHead>Description</TableHead>
                <TableHead className="text-right">Debit</TableHead>
                <TableHead className="text-right">Credit</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {entry.lines.map((line) => (
                <TableRow key={line.id}>
                  <TableCell className="font-medium">{accountLabel(line.account_id)}</TableCell>
                  <TableCell className="text-muted-foreground">{line.description || "—"}</TableCell>
                  <TableCell className="text-right">{line.debit > 0 ? line.debit.toFixed(2) : "—"}</TableCell>
                  <TableCell className="text-right">
                    {line.credit > 0 ? line.credit.toFixed(2) : "—"}
                  </TableCell>
                </TableRow>
              ))}
              <TableRow>
                <TableCell className="font-semibold" colSpan={2}>
                  Total
                </TableCell>
                <TableCell className="text-right font-semibold">{totalDebit.toFixed(2)}</TableCell>
                <TableCell className="text-right font-semibold">{totalCredit.toFixed(2)}</TableCell>
              </TableRow>
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  );
}
