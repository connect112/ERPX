import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { AuditActionBadge } from "@/features/audit/components/audit-action-badge";
import type { AuditChangeValue, AuditLogPublic } from "@/features/audit/api/audit-api";

function formatValue(value: unknown): string {
  if (value === null || value === undefined) return "—";
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
}

function isChangeValue(value: unknown): value is AuditChangeValue {
  return typeof value === "object" && value !== null && "old" in value && "new" in value;
}

interface AuditChangesDialogProps {
  log: AuditLogPublic | null;
  onOpenChange: (open: boolean) => void;
}

export function AuditChangesDialog({ log, onOpenChange }: AuditChangesDialogProps) {
  const fields = log ? Object.entries(log.changes) : [];
  const isDiff = log?.action === "update";

  return (
    <Dialog open={!!log} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            {log && <AuditActionBadge action={log.action} />}
            {log?.entity_type}
            {log?.entity_id ? ` #${log.entity_id.slice(0, 8)}` : ""}
          </DialogTitle>
        </DialogHeader>

        {log && (
          <div className="space-y-4">
            <div className="grid grid-cols-2 gap-2 text-sm text-muted-foreground">
              <div>
                By {log.user_full_name ?? log.user_email ?? "System"}
              </div>
              <div className="text-right">{new Date(log.created_at).toLocaleString()}</div>
              {log.ip_address && <div>IP: {log.ip_address}</div>}
              {log.request_id && <div className="text-right">Request: {log.request_id.slice(0, 8)}</div>}
            </div>

            {fields.length === 0 ? (
              <p className="py-4 text-center text-sm text-muted-foreground">No field-level changes recorded.</p>
            ) : (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Field</TableHead>
                    {isDiff ? (
                      <>
                        <TableHead>Before</TableHead>
                        <TableHead>After</TableHead>
                      </>
                    ) : (
                      <TableHead>Value</TableHead>
                    )}
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {fields.map(([field, value]) => (
                    <TableRow key={field}>
                      <TableCell className="font-medium">{field}</TableCell>
                      {isDiff && isChangeValue(value) ? (
                        <>
                          <TableCell className="text-muted-foreground line-through">
                            {formatValue(value.old)}
                          </TableCell>
                          <TableCell>{formatValue(value.new)}</TableCell>
                        </>
                      ) : (
                        <TableCell>{formatValue(value)}</TableCell>
                      )}
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}
