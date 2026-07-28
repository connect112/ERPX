import { Plus, Search } from "lucide-react";
import { useState } from "react";
import { useNavigate } from "react-router-dom";

import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
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
import { useEmployeesList } from "@/features/employees/api/employees-hooks";
import { EmployeeFormDialog } from "@/features/employees/components/employee-form-dialog";
import { EmployeeStatusBadge } from "@/features/employees/components/employee-status-badge";
import {
  type EmploymentStatus,
  employmentStatusLabels,
  employmentStatusValues,
} from "@/features/employees/schemas/employee-schemas";

const PAGE_SIZE = 20;

export function EmployeesListPage() {
  const navigate = useNavigate();
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState<EmploymentStatus | "all">("all");
  const [skip, setSkip] = useState(0);
  const [formOpen, setFormOpen] = useState(false);

  const { data, isLoading, isError } = useEmployeesList({
    search: search || undefined,
    employment_status: status === "all" ? undefined : status,
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
          <h1 className="text-2xl font-semibold tracking-tight">Employees</h1>
          <p className="mt-1 text-muted-foreground">
            Manage your workforce across every department and branch.
          </p>
        </div>
        <Button onClick={() => setFormOpen(true)}>
          <Plus className="h-4 w-4" />
          New Employee
        </Button>
      </div>

      <Card>
        <CardContent className="space-y-4 p-6">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
            <div className="relative flex-1">
              <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
              <Input
                placeholder="Search by name, code, email, or phone..."
                className="pl-9"
                value={search}
                onChange={(e) => {
                  setSearch(e.target.value);
                  setSkip(0);
                }}
              />
            </div>
            <Select
              value={status}
              onValueChange={(value) => {
                setStatus(value as EmploymentStatus | "all");
                setSkip(0);
              }}
            >
              <SelectTrigger className="sm:w-48">
                <SelectValue placeholder="All statuses" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All statuses</SelectItem>
                {employmentStatusValues.map((s) => (
                  <SelectItem key={s} value={s}>
                    {employmentStatusLabels[s]}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {isLoading && (
            <div className="space-y-2">
              {Array.from({ length: 5 }).map((_, i) => (
                <Skeleton key={i} className="h-12 w-full" />
              ))}
            </div>
          )}

          {isError && (
            <p className="py-8 text-center text-sm text-destructive">
              Failed to load employees. Please try again.
            </p>
          )}

          {!isLoading && !isError && (data?.items.length ?? 0) === 0 && (
            <p className="py-8 text-center text-sm text-muted-foreground">
              No employees found. Add your first employee to get started.
            </p>
          )}

          {!isLoading && !isError && (data?.items.length ?? 0) > 0 && (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Code</TableHead>
                  <TableHead>Name</TableHead>
                  <TableHead>Contact</TableHead>
                  <TableHead>Employment type</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Joined</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {data?.items.map((employee) => (
                  <TableRow
                    key={employee.id}
                    className="cursor-pointer"
                    onClick={() => navigate(`/employees/${employee.id}`)}
                  >
                    <TableCell className="font-mono text-xs text-muted-foreground">
                      {employee.employee_code}
                    </TableCell>
                    <TableCell className="font-medium">{employee.full_name}</TableCell>
                    <TableCell className="text-muted-foreground">
                      {employee.email || employee.phone || "—"}
                    </TableCell>
                    <TableCell className="text-muted-foreground">
                      {employee.employment_type.replace("_", " ")}
                    </TableCell>
                    <TableCell>
                      <EmployeeStatusBadge status={employee.employment_status} />
                    </TableCell>
                    <TableCell className="text-muted-foreground">
                      {new Date(employee.date_of_joining).toLocaleDateString()}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}

          {!isLoading && total > PAGE_SIZE && (
            <div className="flex items-center justify-between pt-2">
              <p className="text-sm text-muted-foreground">
                Page {page} of {pageCount} ({total} employees)
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

      <EmployeeFormDialog open={formOpen} onOpenChange={setFormOpen} />
    </div>
  );
}
