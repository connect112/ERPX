import { useState } from "react";

import { Badge } from "@/components/ui/badge";
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
import { useSalaryComponents } from "@/features/payroll/api/payroll-hooks";
import { useEmployeePayslips, useEmployeeSalaryStructures } from "@/features/payroll/api/payroll-hooks";
import { SalaryStructureFormDialog } from "@/features/payroll/components/salary-structure-form-dialog";

export function EmployeePayrollPanel({ employeeId }: { employeeId: string }) {
  const { data: structures, isLoading: structuresLoading } = useEmployeeSalaryStructures(employeeId);
  const { data: payslips, isLoading: payslipsLoading } = useEmployeePayslips(employeeId, { limit: 20 });
  const { data: components } = useSalaryComponents();
  const [structureOpen, setStructureOpen] = useState(false);

  const componentName = (id: string) => components?.find((c) => c.id === id)?.name ?? id;
  const activeStructure = structures?.find((s) => s.is_active);

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader className="flex flex-row items-center justify-between space-y-0">
          <CardTitle className="text-base">Salary structure</CardTitle>
          <Button size="sm" onClick={() => setStructureOpen(true)}>
            New structure
          </Button>
        </CardHeader>
        <CardContent>
          {structuresLoading && <Skeleton className="h-24 w-full" />}
          {!structuresLoading && !activeStructure && (
            <p className="py-4 text-center text-sm text-muted-foreground">
              No active salary structure.
            </p>
          )}
          {activeStructure && (
            <div className="space-y-4">
              <div className="flex items-center justify-between text-sm">
                <span className="text-muted-foreground">
                  Effective from {new Date(activeStructure.effective_from).toLocaleDateString()}
                </span>
                <Badge variant="success">Active</Badge>
              </div>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Component</TableHead>
                    <TableHead className="text-right">Amount</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {activeStructure.lines.map((line) => (
                    <TableRow key={line.id}>
                      <TableCell>{componentName(line.salary_component_id)}</TableCell>
                      <TableCell className="text-right">{line.amount.toLocaleString()}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
              <div className="grid grid-cols-3 gap-4 pt-2 text-sm">
                <div>
                  <p className="text-xs text-muted-foreground">Gross</p>
                  <p className="font-semibold">{activeStructure.gross_monthly_amount.toLocaleString()}</p>
                </div>
                <div>
                  <p className="text-xs text-muted-foreground">Deductions</p>
                  <p className="font-semibold">{activeStructure.total_deductions.toLocaleString()}</p>
                </div>
                <div>
                  <p className="text-xs text-muted-foreground">Net</p>
                  <p className="font-semibold">{activeStructure.net_monthly_amount.toLocaleString()}</p>
                </div>
              </div>
            </div>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Payslips</CardTitle>
        </CardHeader>
        <CardContent>
          {payslipsLoading && <Skeleton className="h-32 w-full" />}
          {!payslipsLoading && (payslips?.items.length ?? 0) === 0 && (
            <p className="py-4 text-center text-sm text-muted-foreground">No payslips yet.</p>
          )}
          {!payslipsLoading && (payslips?.items.length ?? 0) > 0 && (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Paid days</TableHead>
                  <TableHead>LOP days</TableHead>
                  <TableHead>Gross</TableHead>
                  <TableHead>Deductions</TableHead>
                  <TableHead>Net</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {payslips?.items.map((payslip) => (
                  <TableRow key={payslip.id}>
                    <TableCell className="text-muted-foreground">{payslip.paid_days}</TableCell>
                    <TableCell className="text-muted-foreground">{payslip.lop_days}</TableCell>
                    <TableCell className="text-muted-foreground">
                      {payslip.gross_amount.toLocaleString()}
                    </TableCell>
                    <TableCell className="text-muted-foreground">
                      {payslip.total_deductions.toLocaleString()}
                    </TableCell>
                    <TableCell className="font-medium">{payslip.net_amount.toLocaleString()}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      <SalaryStructureFormDialog
        open={structureOpen}
        onOpenChange={setStructureOpen}
        employeeId={employeeId}
      />
    </div>
  );
}
