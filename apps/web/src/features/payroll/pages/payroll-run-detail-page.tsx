import { ArrowLeft } from "lucide-react";
import { type ReactNode, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
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
import { useAccountsList } from "@/features/accounting/ledger/api/accounts-hooks";
import { useBankAccounts } from "@/features/accounting/bank/api/bank-hooks";
import { useEmployeesList } from "@/features/employees/api/employees-hooks";
import {
  useAddPayslipLine,
  useCancelPayrollRun,
  useDeletePayrollRun,
  useFinalizePayrollRun,
  useMarkPayrollRunPaid,
  useOpenPayslipPdf,
  usePayrollRun,
  useRunPayslips,
  useSalaryComponents,
} from "@/features/payroll/api/payroll-hooks";
import { PayrollRunStatusBadge } from "@/features/payroll/components/payroll-run-status-badge";

const monthNames = [
  "January", "February", "March", "April", "May", "June",
  "July", "August", "September", "October", "November", "December",
];

function DetailRow({ label, value }: { label: string; value: ReactNode }) {
  return (
    <div className="flex items-center justify-between border-b py-3 last:border-0">
      <span className="text-sm text-muted-foreground">{label}</span>
      <span className="text-sm font-medium">{value}</span>
    </div>
  );
}

function todayIso() {
  return new Date().toISOString().slice(0, 10);
}

export function PayrollRunDetailPage() {
  const { runId } = useParams<{ runId: string }>();
  const navigate = useNavigate();
  const { data: run, isLoading } = usePayrollRun(runId);
  const { data: payslips, isLoading: payslipsLoading } = useRunPayslips(runId);
  const { data: employees } = useEmployeesList({ limit: 200 });
  const { data: accounts } = useAccountsList({ limit: 200 });
  const { data: bankAccounts } = useBankAccounts(true);
  const { data: components } = useSalaryComponents(true);

  const finalizeRun = useFinalizePayrollRun(runId ?? "");
  const markPaid = useMarkPayrollRunPaid(runId ?? "");
  const cancelRun = useCancelPayrollRun(runId ?? "");
  const deleteRun = useDeletePayrollRun(runId ?? "");
  const openPayslipPdf = useOpenPayslipPdf();
  const addPayslipLine = useAddPayslipLine(runId ?? "");

  const [finalizeOpen, setFinalizeOpen] = useState(false);
  const [netPayableAccountId, setNetPayableAccountId] = useState("");
  const [markPaidOpen, setMarkPaidOpen] = useState(false);
  const [bankAccountId, setBankAccountId] = useState("");
  const [paymentDate, setPaymentDate] = useState(todayIso());
  const [cancelOpen, setCancelOpen] = useState(false);
  const [deleteOpen, setDeleteOpen] = useState(false);
  const [addLinePayslipId, setAddLinePayslipId] = useState<string | null>(null);
  const [addLineComponentId, setAddLineComponentId] = useState("");
  const [addLineAmount, setAddLineAmount] = useState("");

  const employeeName = (id: string) => employees?.items.find((e) => e.id === id)?.full_name ?? id;

  const handleAddLine = () => {
    if (!addLinePayslipId || !addLineComponentId || !addLineAmount) return;
    addPayslipLine.mutate(
      { payslipId: addLinePayslipId, payload: { salary_component_id: addLineComponentId, amount: Number(addLineAmount) } },
      {
        onSuccess: () => {
          setAddLinePayslipId(null);
          setAddLineComponentId("");
          setAddLineAmount("");
        },
      }
    );
  };

  if (isLoading || !run) {
    return (
      <div className="space-y-4 p-8">
        <Skeleton className="h-8 w-64" />
        <Skeleton className="h-64 w-full" />
      </div>
    );
  }

  const handleFinalize = () => {
    if (!netPayableAccountId) return;
    finalizeRun.mutate(netPayableAccountId, { onSuccess: () => setFinalizeOpen(false) });
  };

  const handleMarkPaid = () => {
    if (!bankAccountId || !paymentDate) return;
    markPaid.mutate(
      { bankAccountId, paymentDate },
      { onSuccess: () => setMarkPaidOpen(false) }
    );
  };

  const handleCancel = () => {
    cancelRun.mutate(undefined, { onSuccess: () => setCancelOpen(false) });
  };

  const handleDelete = () => {
    deleteRun.mutate(undefined, { onSuccess: () => navigate("/payroll/runs") });
  };

  return (
    <div className="space-y-6 p-8">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Button variant="ghost" size="icon" onClick={() => navigate("/payroll/runs")}>
            <ArrowLeft className="h-4 w-4" />
          </Button>
          <div>
            <h1 className="text-2xl font-semibold tracking-tight">
              {monthNames[run.period_month - 1]} {run.period_year} Payroll
            </h1>
            <div className="mt-1">
              <PayrollRunStatusBadge status={run.status} />
            </div>
          </div>
        </div>
        <div className="flex gap-2">
          {run.status === "draft" && (
            <>
              <Button variant="outline" onClick={() => setFinalizeOpen(true)}>
                Finalize
              </Button>
              <Button variant="outline" onClick={() => setCancelOpen(true)}>
                Cancel
              </Button>
            </>
          )}
          {run.status === "finalized" && (
            <>
              <Button variant="outline" onClick={() => setMarkPaidOpen(true)}>
                Mark paid
              </Button>
              <Button variant="outline" onClick={() => setCancelOpen(true)}>
                Cancel
              </Button>
            </>
          )}
          {run.status === "cancelled" && (
            <Button variant="destructive" onClick={() => setDeleteOpen(true)}>
              Delete
            </Button>
          )}
        </div>
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle className="text-base">Summary</CardTitle>
          </CardHeader>
          <CardContent>
            <DetailRow label="Run date" value={new Date(run.run_date).toLocaleDateString()} />
            <DetailRow label="Gross amount" value={run.total_gross_amount.toLocaleString()} />
            <DetailRow label="Deductions" value={run.total_deductions_amount.toLocaleString()} />
            <DetailRow label="Net amount" value={run.total_net_amount.toLocaleString()} />
            {run.finalized_at && (
              <DetailRow label="Finalized at" value={new Date(run.finalized_at).toLocaleString()} />
            )}
            {run.paid_at && <DetailRow label="Paid at" value={new Date(run.paid_at).toLocaleString()} />}
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Payslips</CardTitle>
        </CardHeader>
        <CardContent>
          {payslipsLoading && <Skeleton className="h-32 w-full" />}
          {!payslipsLoading && (payslips?.length ?? 0) === 0 && (
            <p className="py-4 text-center text-sm text-muted-foreground">No payslips generated.</p>
          )}
          {!payslipsLoading && (payslips?.length ?? 0) > 0 && (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Employee</TableHead>
                  <TableHead>Paid days</TableHead>
                  <TableHead>LOP days</TableHead>
                  <TableHead>Gross</TableHead>
                  <TableHead>Deductions</TableHead>
                  <TableHead>Net</TableHead>
                  <TableHead />
                </TableRow>
              </TableHeader>
              <TableBody>
                {payslips?.map((payslip) => (
                  <TableRow key={payslip.id}>
                    <TableCell className="font-medium">{employeeName(payslip.employee_id)}</TableCell>
                    <TableCell className="text-muted-foreground">{payslip.paid_days}</TableCell>
                    <TableCell className="text-muted-foreground">{payslip.lop_days}</TableCell>
                    <TableCell className="text-muted-foreground">
                      {payslip.gross_amount.toLocaleString()}
                    </TableCell>
                    <TableCell className="text-muted-foreground">
                      {payslip.total_deductions.toLocaleString()}
                    </TableCell>
                    <TableCell className="font-medium">{payslip.net_amount.toLocaleString()}</TableCell>
                    <TableCell className="text-right">
                      <div className="flex justify-end gap-1">
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => openPayslipPdf.mutate(payslip.id)}
                          disabled={openPayslipPdf.isPending}
                        >
                          View PDF
                        </Button>
                        {run.status === "draft" && (
                          <Button variant="ghost" size="sm" onClick={() => setAddLinePayslipId(payslip.id)}>
                            Add line
                          </Button>
                        )}
                      </div>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      <Dialog open={finalizeOpen} onOpenChange={setFinalizeOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Finalize payroll run</DialogTitle>
          </DialogHeader>
          <div className="space-y-2">
            <Label htmlFor="netPayableAccountId">Net payable account</Label>
            <Select value={netPayableAccountId || undefined} onValueChange={setNetPayableAccountId}>
              <SelectTrigger id="netPayableAccountId">
                <SelectValue placeholder="Select GL account" />
              </SelectTrigger>
              <SelectContent>
                {accounts?.items.map((a) => (
                  <SelectItem key={a.id} value={a.id}>
                    {a.code} — {a.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setFinalizeOpen(false)}>
              Cancel
            </Button>
            <Button onClick={handleFinalize} disabled={!netPayableAccountId || finalizeRun.isPending}>
              {finalizeRun.isPending ? "Finalizing..." : "Finalize"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={markPaidOpen} onOpenChange={setMarkPaidOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Mark payroll run as paid</DialogTitle>
          </DialogHeader>
          <div className="space-y-2">
            <Label htmlFor="bankAccountId">Bank account</Label>
            <Select value={bankAccountId || undefined} onValueChange={setBankAccountId}>
              <SelectTrigger id="bankAccountId">
                <SelectValue placeholder="Select bank account" />
              </SelectTrigger>
              <SelectContent>
                {bankAccounts?.map((b) => (
                  <SelectItem key={b.id} value={b.id}>
                    {b.account_name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-2">
            <Label htmlFor="paymentDate">Payment date</Label>
            <Input
              id="paymentDate"
              type="date"
              value={paymentDate}
              onChange={(e) => setPaymentDate(e.target.value)}
            />
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setMarkPaidOpen(false)}>
              Cancel
            </Button>
            <Button onClick={handleMarkPaid} disabled={!bankAccountId || markPaid.isPending}>
              {markPaid.isPending ? "Saving..." : "Mark paid"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={cancelOpen} onOpenChange={setCancelOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Cancel payroll run</DialogTitle>
          </DialogHeader>
          <p className="text-sm text-muted-foreground">
            Are you sure you want to cancel this payroll run? This action cannot be undone.
          </p>
          <DialogFooter>
            <Button variant="outline" onClick={() => setCancelOpen(false)}>
              Keep run
            </Button>
            <Button variant="destructive" onClick={handleCancel} disabled={cancelRun.isPending}>
              {cancelRun.isPending ? "Cancelling..." : "Cancel run"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={deleteOpen} onOpenChange={setDeleteOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Delete payroll run</DialogTitle>
          </DialogHeader>
          <p className="text-sm text-muted-foreground">
            Permanently deletes this cancelled run and its payslips, and frees up its period so
            you can generate a fresh run for {monthNames[run.period_month - 1]} {run.period_year}.
            This cannot be undone.
          </p>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDeleteOpen(false)}>
              Keep run
            </Button>
            <Button variant="destructive" onClick={handleDelete} disabled={deleteRun.isPending}>
              {deleteRun.isPending ? "Deleting..." : "Delete run"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={!!addLinePayslipId} onOpenChange={(open) => !open && setAddLinePayslipId(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Add a one-off line</DialogTitle>
          </DialogHeader>
          <p className="text-sm text-muted-foreground">
            Applies to this employee's payslip for this run only — e.g. a reimbursement that
            isn't part of their regular salary structure.
          </p>
          <div className="space-y-2">
            <Label htmlFor="addLineComponent">Component</Label>
            <Select value={addLineComponentId || undefined} onValueChange={setAddLineComponentId}>
              <SelectTrigger id="addLineComponent">
                <SelectValue placeholder="Select component" />
              </SelectTrigger>
              <SelectContent>
                {components?.map((c) => (
                  <SelectItem key={c.id} value={c.id}>
                    {c.name} ({c.component_type})
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-2">
            <Label htmlFor="addLineAmount">Amount</Label>
            <Input
              id="addLineAmount"
              type="number"
              min="0"
              step="0.01"
              value={addLineAmount}
              onChange={(e) => setAddLineAmount(e.target.value)}
            />
          </div>
          {addPayslipLine.isError && (
            <p className="text-sm text-destructive">
              {(addPayslipLine.error as { response?: { data?: { error?: { message?: string } } } })?.response
                ?.data?.error?.message ?? "Could not add this line."}
            </p>
          )}
          <DialogFooter>
            <Button variant="outline" onClick={() => setAddLinePayslipId(null)}>
              Cancel
            </Button>
            <Button
              onClick={handleAddLine}
              disabled={!addLineComponentId || !addLineAmount || addPayslipLine.isPending}
            >
              {addPayslipLine.isPending ? "Adding..." : "Add line"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
