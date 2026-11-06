import { useQuery } from "@tanstack/react-query";
import { Download, Eye, History } from "lucide-react";
import { useEffect, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { errorMessage } from "@/features/institutions/lib/format";
import { PdfPane } from "@/features/internship-onboarding/components/pdf-pane";
import { inZone, money, statusLabel } from "@/features/internship-onboarding/lib/format";
import { KIND_LABELS } from "@/features/internship-onboarding/lib/receipt-design";
import { type ReceiptFilters, type ReceiptKind, type ReceiptRow, receiptsApi } from "@/features/internship-onboarding/receipts-api";

const PAGE = 25;
const selectClass = "rounded-md border bg-background px-3 py-2 text-sm";
const EMAIL: Record<string, { label: string; tone: "success" | "warning" | "destructive" | "secondary" }> = {
  sent: { label: "Sent", tone: "success" },
  pending: { label: "Sending", tone: "warning" },
  failed: { label: "Failed", tone: "destructive" },
  none: { label: "Not emailed", tone: "secondary" },
};

/** Saves a blob under a name through a temporary link (revoked straight away). */
export function saveBlob(blob: Blob, name: string): void {
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = name;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

function Viewer({ internshipId, row, onClose }: { internshipId: string; row: ReceiptRow; onClose: () => void }) {
  const file = useQuery({ queryKey: ["receipt-pdf", internshipId, row.id], queryFn: () => receiptsApi.receiptPdf(internshipId, row.id), staleTime: Infinity, gcTime: 0 });
  return (
    <Dialog open onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="max-w-4xl">
        <DialogHeader>
          <DialogTitle>
            {KIND_LABELS[row.kind]} {row.number}
          </DialogTitle>
          <DialogDescription>The document exactly as it was issued. It is never redrawn.</DialogDescription>
        </DialogHeader>
        <PdfPane
          title={row.number}
          blob={file.data ?? null}
          pages={row.pages}
          filename={`${row.number}.pdf`}
          loading={file.isLoading}
          error={file.isError ? errorMessage(file.error, "The document could not be opened.") : null}
        />
      </DialogContent>
    </Dialog>
  );
}

function HistoryDialog({ internshipId, row, onClose }: { internshipId: string; row: ReceiptRow; onClose: () => void }) {
  const history = useQuery({ queryKey: ["receipt-history", internshipId, row.id], queryFn: () => receiptsApi.history(internshipId, row.id) });
  const h = history.data;
  return (
    <Dialog open onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle>Issuance history · {row.number}</DialogTitle>
          <DialogDescription>How this document came to be. Nothing here can be edited.</DialogDescription>
        </DialogHeader>
        {history.isError && <p className="text-sm text-destructive">{errorMessage(history.error, "Could not load the history.")}</p>}
        {h && (
          <div className="space-y-4 text-sm">
            <section className="space-y-1">
              <h3 className="font-semibold">Linked payment</h3>
              {h.transaction ? (
                <p>
                  {h.transaction.kind} · {money(h.transaction.amount, h.transaction.currency)} · {h.transaction.method ?? "-"} · reference {h.transaction.reference ?? "-"} ·{" "}
                  <Badge variant="secondary">{statusLabel(h.transaction.status)}</Badge>
                  {h.transaction.paid_on ? ` · paid ${h.transaction.paid_on}` : ""}
                </p>
              ) : (
                <p className="text-muted-foreground">No linked payment.</p>
              )}
            </section>
            <section className="space-y-1">
              <h3 className="font-semibold">Design used</h3>
              <p>
                {h.design.engine === "legacy"
                  ? "Issued with the original layout (before the Receipt Designer)."
                  : `${h.design.source ?? "built-in"} design, version ${h.design.version ?? 0}, ${h.design.pages ?? 1} page${h.design.pages === 1 ? "" : "s"}.`}
              </p>
              <p className="break-all text-xs text-muted-foreground">Checksum (SHA-256): {h.document.sha256}</p>
            </section>
            <section className="space-y-1">
              <h3 className="font-semibold">Delivery</h3>
              <p>
                {EMAIL[h.delivery.status]?.label ?? h.delivery.status} · {h.delivery.attempts} attempt{h.delivery.attempts === 1 ? "" : "s"}
                {h.delivery.emailed_at ? ` · ${new Date(h.delivery.emailed_at).toLocaleString()}` : ""}
              </p>
            </section>
            <section className="space-y-1">
              <h3 className="font-semibold">Timeline</h3>
              <ul className="space-y-0.5 text-xs">
                {h.events.map((e, i) => (
                  <li key={i}>
                    <span className="text-muted-foreground">{new Date(e.at).toLocaleString()}</span> · {e.actor} · {e.event.replace(/_/g, " ")}
                  </li>
                ))}
              </ul>
            </section>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}

/** The documents issued for an internship, with search, filters, in-page viewing, download and each one's history. */
export function GeneratedReceipts({ internshipId, timezone }: { internshipId: string; timezone: string }) {
  const [q, setQ] = useState("");
  const [search, setSearch] = useState("");
  const [kind, setKind] = useState<ReceiptKind | "">("");
  const [emailStatus, setEmailStatus] = useState("");
  const [from, setFrom] = useState("");
  const [to, setTo] = useState("");
  const [offset, setOffset] = useState(0);
  const [viewing, setViewing] = useState<ReceiptRow | null>(null);
  const [tracing, setTracing] = useState<ReceiptRow | null>(null);
  const [problem, setProblem] = useState<string | null>(null);

  useEffect(() => {
    const t = setTimeout(() => (setSearch(q.trim()), setOffset(0)), 400);
    return () => clearTimeout(t);
  }, [q]);

  const filters: ReceiptFilters = { q: search, kind, email_status: emailStatus, issued_from: from, issued_to: to, limit: PAGE, offset };
  const list = useQuery({ queryKey: ["receipts", internshipId, filters], queryFn: () => receiptsApi.receipts(internshipId, filters), placeholderData: (previous) => previous });
  const total = list.data?.total ?? 0;

  const download = async (row: ReceiptRow) => {
    try {
      saveBlob(await receiptsApi.receiptPdf(internshipId, row.id, true), `${row.number}.pdf`);
    } catch (e) {
      setProblem(errorMessage(e, "The document could not be downloaded."));
    }
  };
  const reset = <T,>(set: (v: T) => void) => (v: T) => (set(v), setOffset(0));

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-end gap-2">
        <Input aria-label="Search receipts" className="max-w-xs" placeholder="Search number, student, email, reference" value={q} onChange={(e) => setQ(e.target.value)} />
        <select aria-label="Document type" className={selectClass} value={kind} onChange={(e) => reset(setKind)(e.target.value as ReceiptKind | "")}>
          <option value="">All types</option>
          {(Object.keys(KIND_LABELS) as ReceiptKind[]).map((k) => (
            <option key={k} value={k}>
              {KIND_LABELS[k]}
            </option>
          ))}
        </select>
        <select aria-label="Email status" className={selectClass} value={emailStatus} onChange={(e) => reset(setEmailStatus)(e.target.value)}>
          <option value="">Any email status</option>
          {Object.entries(EMAIL).map(([k, v]) => (
            <option key={k} value={k}>
              {v.label}
            </option>
          ))}
        </select>
        <label className="text-xs text-muted-foreground">
          Issued from
          <Input type="date" aria-label="Issued from" value={from} onChange={(e) => reset(setFrom)(e.target.value)} />
        </label>
        <label className="text-xs text-muted-foreground">
          to
          <Input type="date" aria-label="Issued to" value={to} onChange={(e) => reset(setTo)(e.target.value)} />
        </label>
      </div>
      {problem && (
        <p className="text-sm text-destructive" role="alert">
          {problem}
        </p>
      )}
      {list.isError && <p className="text-sm text-destructive">{errorMessage(list.error, "Could not load the receipts.")}</p>}
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Number</TableHead>
            <TableHead>Type</TableHead>
            <TableHead>Student</TableHead>
            <TableHead>Internship</TableHead>
            <TableHead className="text-right">Amount</TableHead>
            <TableHead>Payment date</TableHead>
            <TableHead>Email</TableHead>
            <TableHead>Created</TableHead>
            <TableHead className="text-right">Actions</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {(list.data?.items ?? []).map((row) => (
            <TableRow key={row.id}>
              <TableCell className="font-mono text-xs">{row.number}</TableCell>
              <TableCell>{KIND_LABELS[row.kind]}</TableCell>
              <TableCell>
                <div>{row.student}</div>
                <div className="text-xs text-muted-foreground">{row.application}</div>
              </TableCell>
              <TableCell>{row.internship}</TableCell>
              <TableCell className="text-right">{money(row.amount, row.currency)}</TableCell>
              <TableCell>{row.paid_on ?? "-"}</TableCell>
              <TableCell>
                <Badge variant={EMAIL[row.email_status]?.tone ?? "secondary"}>{EMAIL[row.email_status]?.label ?? row.email_status}</Badge>
              </TableCell>
              <TableCell className="text-xs">{inZone(row.issued_at, timezone)}</TableCell>
              <TableCell className="text-right">
                <Button size="sm" variant="ghost" aria-label={`View ${row.number}`} onClick={() => setViewing(row)}>
                  <Eye className="h-4 w-4" />
                </Button>
                <Button size="sm" variant="ghost" aria-label={`Download ${row.number}`} onClick={() => void download(row)}>
                  <Download className="h-4 w-4" />
                </Button>
                <Button size="sm" variant="ghost" aria-label={`History and payment of ${row.number}`} onClick={() => setTracing(row)}>
                  <History className="h-4 w-4" />
                </Button>
              </TableCell>
            </TableRow>
          ))}
          {list.data && list.data.items.length === 0 && (
            <TableRow>
              <TableCell colSpan={9} className="text-center text-sm text-muted-foreground">
                No documents match.
              </TableCell>
            </TableRow>
          )}
        </TableBody>
      </Table>
      <div className="flex items-center justify-between text-sm text-muted-foreground">
        <span>
          {total === 0 ? "0 documents" : `${offset + 1}–${Math.min(offset + PAGE, total)} of ${total}`}
        </span>
        <span className="flex gap-2">
          <Button size="sm" variant="outline" disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - PAGE))}>
            Previous
          </Button>
          <Button size="sm" variant="outline" disabled={offset + PAGE >= total} onClick={() => setOffset(offset + PAGE)}>
            Next
          </Button>
        </span>
      </div>
      {viewing && <Viewer internshipId={internshipId} row={viewing} onClose={() => setViewing(null)} />}
      {tracing && <HistoryDialog internshipId={internshipId} row={tracing} onClose={() => setTracing(null)} />}
    </div>
  );
}
