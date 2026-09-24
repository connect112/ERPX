import { format, parseISO } from "date-fns";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { useMyPayslips } from "@/features/payslips/api/payslips-hooks";
import type { Payslip } from "@/features/payslips/api/payslips-api";

function formatAmount(value: number): string {
  return new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", maximumFractionDigits: 0 }).format(
    value
  );
}

function PayslipRow({ payslip }: { payslip: Payslip }) {
  const earnings = payslip.lines.filter((l) => l.component_type === "earning");
  const deductions = payslip.lines.filter((l) => l.component_type === "deduction");

  return (
    <TableRow>
      <TableCell className="font-medium">{format(parseISO(payslip.created_at), "PPP")}</TableCell>
      <TableCell>
        {payslip.paid_days} / {payslip.days_in_month} days
        {payslip.lop_days > 0 && (
          <span className="text-muted-foreground"> ({payslip.lop_days} LOP)</span>
        )}
      </TableCell>
      <TableCell>{formatAmount(payslip.gross_amount)}</TableCell>
      <TableCell>{formatAmount(payslip.total_deductions)}</TableCell>
      <TableCell className="font-semibold">{formatAmount(payslip.net_amount)}</TableCell>
      <TableCell>
        <div className="flex flex-wrap gap-1">
          {earnings.map((l) => (
            <Badge key={l.id} variant="success" className="text-xs">
              +{formatAmount(l.amount)}
            </Badge>
          ))}
          {deductions.map((l) => (
            <Badge key={l.id} variant="outline" className="text-xs">
              -{formatAmount(l.amount)}
            </Badge>
          ))}
        </div>
      </TableCell>
    </TableRow>
  );
}

export function MyPayslipsPage() {
  const { data, isLoading, isError } = useMyPayslips();
  const payslips = data?.items ?? [];

  return (
    <div className="space-y-6 p-6">
      <div>
        <h1 className="text-2xl font-semibold">My Payslips</h1>
        <p className="text-sm text-muted-foreground">
          Every payslip issued to you, most recent first. Reach out to HR for questions about a
          specific line item.
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Payslip history</CardTitle>
          <CardDescription>Gross pay, deductions, and net amount for each payroll run.</CardDescription>
        </CardHeader>
        <CardContent className="p-0">
          {isLoading ? (
            <div className="space-y-2 p-6">
              <Skeleton className="h-10 w-full" />
              <Skeleton className="h-10 w-full" />
            </div>
          ) : isError ? (
            <p className="p-6 text-center text-sm text-destructive">Failed to load payslips.</p>
          ) : payslips.length > 0 ? (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Issued</TableHead>
                  <TableHead>Attendance</TableHead>
                  <TableHead>Gross</TableHead>
                  <TableHead>Deductions</TableHead>
                  <TableHead>Net pay</TableHead>
                  <TableHead>Breakdown</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {payslips.map((p) => (
                  <PayslipRow key={p.id} payslip={p} />
                ))}
              </TableBody>
            </Table>
          ) : (
            <p className="p-6 text-center text-sm text-muted-foreground">
              No payslips yet — they'll appear here once payroll has been run.
            </p>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
