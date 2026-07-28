import { ArrowLeft, Pencil, Trash2 } from "lucide-react";
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
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  useChangeEmployeeStatus,
  useDeleteEmployee,
  useEmployee,
  useEmployeesList,
} from "@/features/employees/api/employees-hooks";
import { EmployeeFormDialog } from "@/features/employees/components/employee-form-dialog";
import { EmployeeStatusBadge } from "@/features/employees/components/employee-status-badge";
import {
  type EmploymentStatus,
  employmentStatusLabels,
  employmentStatusValues,
  employmentTypeLabels,
  genderLabels,
} from "@/features/employees/schemas/employee-schemas";
import { useDepartments, useDesignations } from "@/features/hr/api/hr-hooks";
import { EmployeeAttendancePanel } from "@/features/attendance/components/employee-attendance-panel";
import { EmployeeLeavePanel } from "@/features/leave/components/employee-leave-panel";
import { EmployeePayrollPanel } from "@/features/payroll/components/employee-payroll-panel";

function DetailRow({ label, value }: { label: string; value: ReactNode }) {
  return (
    <div className="flex items-center justify-between border-b py-3 last:border-0">
      <span className="text-sm text-muted-foreground">{label}</span>
      <span className="text-sm font-medium">{value}</span>
    </div>
  );
}

export function EmployeeDetailPage() {
  const { employeeId } = useParams<{ employeeId: string }>();
  const navigate = useNavigate();
  const { data: employee, isLoading } = useEmployee(employeeId);
  const changeStatus = useChangeEmployeeStatus(employeeId ?? "");
  const deleteEmployee = useDeleteEmployee();
  const { data: departments } = useDepartments();
  const { data: designations } = useDesignations();
  const { data: allEmployees } = useEmployeesList({ limit: 200 });

  const [editOpen, setEditOpen] = useState(false);
  const [deleteOpen, setDeleteOpen] = useState(false);
  const [statusTarget, setStatusTarget] = useState<EmploymentStatus | null>(null);
  const [dateOfExit, setDateOfExit] = useState("");

  if (isLoading || !employee) {
    return (
      <div className="space-y-4 p-8">
        <Skeleton className="h-8 w-64" />
        <Skeleton className="h-64 w-full" />
      </div>
    );
  }

  const departmentName = departments?.find((d) => d.id === employee.department_id)?.name;
  const designationTitle = designations?.find((d) => d.id === employee.designation_id)?.title;
  const managerName = allEmployees?.items.find((e) => e.id === employee.reporting_manager_id)?.full_name;

  const handleDelete = () => {
    deleteEmployee.mutate(employee.id, {
      onSuccess: () => navigate("/employees"),
    });
  };

  const handleConfirmStatus = () => {
    if (!statusTarget) return;
    changeStatus.mutate(
      { status: statusTarget, dateOfExit: dateOfExit || undefined },
      {
        onSuccess: () => {
          setStatusTarget(null);
          setDateOfExit("");
        },
      }
    );
  };

  return (
    <div className="space-y-6 p-8">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Button variant="ghost" size="icon" onClick={() => navigate("/employees")}>
            <ArrowLeft className="h-4 w-4" />
          </Button>
          <div>
            <h1 className="text-2xl font-semibold tracking-tight">{employee.full_name}</h1>
            <div className="mt-1 flex items-center gap-2">
              <span className="font-mono text-xs text-muted-foreground">
                {employee.employee_code}
              </span>
              <EmployeeStatusBadge status={employee.employment_status} />
            </div>
          </div>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" onClick={() => setEditOpen(true)}>
            <Pencil className="h-4 w-4" />
            Edit
          </Button>
          <Button variant="outline" onClick={() => setDeleteOpen(true)}>
            <Trash2 className="h-4 w-4" />
            Delete
          </Button>
        </div>
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        <div className="space-y-6 lg:col-span-2">
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Personal details</CardTitle>
            </CardHeader>
            <CardContent>
              <DetailRow label="Email" value={employee.email || "—"} />
              <DetailRow label="Phone" value={employee.phone || "—"} />
              <DetailRow
                label="Gender"
                value={employee.gender ? genderLabels[employee.gender] : "—"}
              />
              <DetailRow
                label="Date of birth"
                value={
                  employee.date_of_birth
                    ? new Date(employee.date_of_birth).toLocaleDateString()
                    : "—"
                }
              />
              <DetailRow
                label="Address"
                value={
                  [employee.address_line1, employee.city, employee.state, employee.country, employee.postal_code]
                    .filter(Boolean)
                    .join(", ") || "—"
                }
              />
              <DetailRow label="Emergency contact" value={employee.emergency_contact_name || "—"} />
              <DetailRow label="Emergency phone" value={employee.emergency_contact_phone || "—"} />
              {employee.notes && (
                <div className="pt-3">
                  <p className="text-sm text-muted-foreground">Notes</p>
                  <p className="mt-1 whitespace-pre-wrap text-sm">{employee.notes}</p>
                </div>
              )}
            </CardContent>
          </Card>
        </div>

        <div className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Employment</CardTitle>
            </CardHeader>
            <CardContent>
              <DetailRow label="Department" value={departmentName || "—"} />
              <DetailRow label="Designation" value={designationTitle || "—"} />
              <DetailRow label="Reporting manager" value={managerName || "—"} />
              <DetailRow label="Employment type" value={employmentTypeLabels[employee.employment_type]} />
              <DetailRow
                label="Date of joining"
                value={new Date(employee.date_of_joining).toLocaleDateString()}
              />
              {employee.date_of_exit && (
                <DetailRow
                  label="Date of exit"
                  value={new Date(employee.date_of_exit).toLocaleDateString()}
                />
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="text-base">Change status</CardTitle>
            </CardHeader>
            <CardContent>
              <Select
                value={employee.employment_status}
                onValueChange={(value) => setStatusTarget(value as EmploymentStatus)}
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {employmentStatusValues.map((s) => (
                    <SelectItem key={s} value={s}>
                      {employmentStatusLabels[s]}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </CardContent>
          </Card>
        </div>
      </div>

      <Tabs defaultValue="attendance">
        <TabsList>
          <TabsTrigger value="attendance">Attendance</TabsTrigger>
          <TabsTrigger value="leave">Leave</TabsTrigger>
          <TabsTrigger value="payroll">Payroll</TabsTrigger>
        </TabsList>
        <TabsContent value="attendance">
          <EmployeeAttendancePanel employeeId={employee.id} />
        </TabsContent>
        <TabsContent value="leave">
          <EmployeeLeavePanel employeeId={employee.id} />
        </TabsContent>
        <TabsContent value="payroll">
          <EmployeePayrollPanel employeeId={employee.id} />
        </TabsContent>
      </Tabs>

      <EmployeeFormDialog open={editOpen} onOpenChange={setEditOpen} employee={employee} />

      <Dialog
        open={!!statusTarget}
        onOpenChange={(open) => {
          if (!open) {
            setStatusTarget(null);
            setDateOfExit("");
          }
        }}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>
              Mark employee as {statusTarget ? employmentStatusLabels[statusTarget] : ""}
            </DialogTitle>
          </DialogHeader>
          {(statusTarget === "resigned" || statusTarget === "terminated" || statusTarget === "retired") && (
            <div className="space-y-2">
              <Label htmlFor="dateOfExit">Date of exit</Label>
              <Input
                id="dateOfExit"
                type="date"
                value={dateOfExit}
                onChange={(e) => setDateOfExit(e.target.value)}
              />
            </div>
          )}
          <DialogFooter>
            <Button variant="outline" onClick={() => setStatusTarget(null)}>
              Cancel
            </Button>
            <Button onClick={handleConfirmStatus} disabled={changeStatus.isPending}>
              {changeStatus.isPending ? "Updating..." : "Confirm"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={deleteOpen} onOpenChange={setDeleteOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Delete employee</DialogTitle>
          </DialogHeader>
          <p className="text-sm text-muted-foreground">
            Are you sure you want to delete{" "}
            <span className="font-medium">{employee.full_name}</span>? This action cannot be undone.
          </p>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDeleteOpen(false)}>
              Cancel
            </Button>
            <Button variant="destructive" onClick={handleDelete} disabled={deleteEmployee.isPending}>
              {deleteEmployee.isPending ? "Deleting..." : "Delete"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
