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
import { GeneratePayrollRunDialog } from "@/features/payroll/components/generate-payroll-run-dialog";
import { PayrollRunStatusBadge } from "@/features/payroll/components/payroll-run-status-badge";
import { usePayrollRuns } from "@/features/payroll/api/payroll-hooks";
import {
  type PayrollRunStatus,
  payrollRunStatusLabels,
  payrollRunStatusValues,
} from "@/features/payroll/schemas/payroll-schemas";

const PAGE_SIZE = 20;
const monthNames = [
  "January", "February", "March", "April", "May", "June",
  "July", "August", "September", "October", "November", "December",
];

export function PayrollRunsPage() {
  const navigate = useNavigate();
  const [status, setStatus] = useState<PayrollRunStatus | "all">("all");
  const [skip, setSkip] = useState(0);
  const [generateOpen, setGenerateOpen] = useState(false);

  const { data, isLoading, isError } = usePayrollRuns({
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
          <h1 className="text-2xl font-semibold tracking-tight">Payroll Runs</h1>
          <p className="mt-1 text-muted-foreground">
            Generate, finalize, and settle monthly payroll runs.
          </p>
        </div>
        <Button onClick={() => setGenerateOpen(true)}>
          <Plus className="h-4 w-4" />
          Generate run
        </Button>
      </div>

      <Card>
        <CardContent className="space-y-4 p-6">
          <Select
            value={status}
            onValueChange={(value) => {
              setStatus(value as PayrollRunStatus | "all");
              setSkip(0);
            }}
          >
            <SelectTrigger className="sm:w-48">
              <SelectValue placeholder="All statuses" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All statuses</SelectItem>
              {payrollRunStatusValues.map((s) => (
                <SelectItem key={s} value={s}>
                  {payrollRunStatusLabels[s]}
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
              Failed to load payroll runs. Please try again.
            </p>
          )}

          {!isLoading && !isError && (data?.items.length ?? 0) === 0 && (
            <p className="py-8 text-center text-sm text-muted-foreground">
              No payroll runs found. Generate your first run to get started.
            </p>
          )}

          {!isLoading && !isError && (data?.items.length ?? 0) > 0 && (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Period</TableHead>
                  <TableHead>Run date</TableHead>
                  <TableHead>Gross</TableHead>
                  <TableHead>Deductions</TableHead>
                  <TableHead>Net</TableHead>
                  <TableHead>Status</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {data?.items.map((run) => (
                  <TableRow
                    key={run.id}
                    className="cursor-pointer"
                    onClick={() => navigate(`/payroll/runs/${run.id}`)}
                  >
                    <TableCell className="font-medium">
                      {monthNames[run.period_month - 1]} {run.period_year}
                    </TableCell>
                    <TableCell className="text-muted-foreground">
                      {new Date(run.run_date).toLocaleDateString()}
                    </TableCell>
                    <TableCell className="text-muted-foreground">
                      {run.total_gross_amount.toLocaleString()}
                    </TableCell>
                    <TableCell className="text-muted-foreground">
                      {run.total_deductions_amount.toLocaleString()}
                    </TableCell>
                    <TableCell className="font-medium">{run.total_net_amount.toLocaleString()}</TableCell>
                    <TableCell>
                      <PayrollRunStatusBadge status={run.status} />
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}

          {!isLoading && total > PAGE_SIZE && (
            <div className="flex items-center justify-between pt-2">
              <p className="text-sm text-muted-foreground">
                Page {page} of {pageCount} ({total} runs)
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

      <GeneratePayrollRunDialog open={generateOpen} onOpenChange={setGenerateOpen} />
    </div>
  );
}
