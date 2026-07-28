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
  useChangeStudentStatus,
  useDeleteStudent,
  useStudent,
} from "@/features/students/api/students-hooks";
import { StudentFormDialog } from "@/features/students/components/student-form-dialog";
import { StudentStatusBadge } from "@/features/students/components/student-status-badge";
import {
  type StudentStatus,
  genderLabels,
  studentStatusLabels,
  studentStatusValues,
} from "@/features/students/schemas/student-schemas";
import { StudentResultsPanel } from "@/features/examinations/results/components/student-results-panel";
import { StudentBadgesPanel } from "@/features/lms/badges/components/student-badges-panel";
import { CertificatesPanel } from "@/features/lms/certificates/components/certificates-panel";
import { EnrollmentsByStudentPanel } from "@/features/lms/enrollment/components/enrollments-by-student-panel";
import { StudentAchievementsPanel } from "@/features/pentrix/achievements/components/student-achievements-panel";
import { StudentCertificationsPanel } from "@/features/pentrix/certifications/components/student-certifications-panel";
import { StudentSolvesPanel } from "@/features/pentrix/flags/components/student-solves-panel";
import { StudentLabInstancesPanel } from "@/features/pentrix/lab-instances/components/student-lab-instances-panel";

function DetailRow({ label, value }: { label: string; value: ReactNode }) {
  return (
    <div className="flex items-center justify-between border-b py-3 last:border-0">
      <span className="text-sm text-muted-foreground">{label}</span>
      <span className="text-sm font-medium">{value}</span>
    </div>
  );
}

export function StudentDetailPage() {
  const { studentId } = useParams<{ studentId: string }>();
  const navigate = useNavigate();
  const { data: student, isLoading } = useStudent(studentId);
  const changeStatus = useChangeStudentStatus(studentId ?? "");
  const deleteStudent = useDeleteStudent();

  const [editOpen, setEditOpen] = useState(false);
  const [deleteOpen, setDeleteOpen] = useState(false);
  const [statusTarget, setStatusTarget] = useState<StudentStatus | null>(null);

  if (isLoading || !student) {
    return (
      <div className="space-y-4 p-8">
        <Skeleton className="h-8 w-64" />
        <Skeleton className="h-64 w-full" />
      </div>
    );
  }

  const handleDelete = () => {
    deleteStudent.mutate(student.id, {
      onSuccess: () => navigate("/students"),
    });
  };

  const handleConfirmStatus = () => {
    if (!statusTarget) return;
    changeStatus.mutate({ status: statusTarget }, { onSuccess: () => setStatusTarget(null) });
  };

  return (
    <div className="space-y-6 p-8">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Button variant="ghost" size="icon" onClick={() => navigate("/students")}>
            <ArrowLeft className="h-4 w-4" />
          </Button>
          <div>
            <h1 className="text-2xl font-semibold tracking-tight">{student.full_name}</h1>
            <div className="mt-1 flex items-center gap-2">
              <span className="font-mono text-xs text-muted-foreground">{student.student_code}</span>
              <StudentStatusBadge status={student.status} />
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
              <DetailRow label="Email" value={student.email || "—"} />
              <DetailRow label="Phone" value={student.phone || "—"} />
              <DetailRow
                label="Gender"
                value={student.gender ? genderLabels[student.gender] : "—"}
              />
              <DetailRow
                label="Date of birth"
                value={
                  student.date_of_birth
                    ? new Date(student.date_of_birth).toLocaleDateString()
                    : "—"
                }
              />
              <DetailRow label="Guardian" value={student.guardian_name || "—"} />
              <DetailRow label="Guardian phone" value={student.guardian_phone || "—"} />
              <DetailRow
                label="Address"
                value={
                  [
                    student.address_line1,
                    student.address_line2,
                    student.city,
                    student.state,
                    student.country,
                    student.postal_code,
                  ]
                    .filter(Boolean)
                    .join(", ") || "—"
                }
              />
              {student.notes && (
                <div className="pt-3">
                  <p className="text-sm text-muted-foreground">Notes</p>
                  <p className="mt-1 whitespace-pre-wrap text-sm">{student.notes}</p>
                </div>
              )}
            </CardContent>
          </Card>
        </div>

        <div className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Course</CardTitle>
            </CardHeader>
            <CardContent>
              <DetailRow label="Course" value={student.course_name} />
              <DetailRow label="Batch" value={student.batch_name || "—"} />
              <DetailRow
                label="Enrolled"
                value={new Date(student.enrollment_date).toLocaleDateString()}
              />
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="text-base">Change status</CardTitle>
            </CardHeader>
            <CardContent>
              <Select
                value={student.status}
                onValueChange={(value) => setStatusTarget(value as StudentStatus)}
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {studentStatusValues.map((s) => (
                    <SelectItem key={s} value={s}>
                      {studentStatusLabels[s]}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </CardContent>
          </Card>
        </div>
      </div>

      <Tabs defaultValue="learning">
        <TabsList>
          <TabsTrigger value="learning">Learning</TabsTrigger>
          <TabsTrigger value="certificates">Certificates</TabsTrigger>
          <TabsTrigger value="badges">Badges</TabsTrigger>
          <TabsTrigger value="results">Results</TabsTrigger>
          <TabsTrigger value="pentrix">Pentrix</TabsTrigger>
        </TabsList>
        <TabsContent value="learning">
          <EnrollmentsByStudentPanel studentId={student.id} />
        </TabsContent>
        <TabsContent value="certificates">
          <CertificatesPanel studentId={student.id} />
        </TabsContent>
        <TabsContent value="badges">
          <StudentBadgesPanel studentId={student.id} />
        </TabsContent>
        <TabsContent value="results">
          <StudentResultsPanel studentId={student.id} />
        </TabsContent>
        <TabsContent value="pentrix" className="space-y-6">
          <StudentLabInstancesPanel studentId={student.id} />
          <StudentSolvesPanel studentId={student.id} />
          <StudentAchievementsPanel studentId={student.id} />
          <StudentCertificationsPanel studentId={student.id} />
        </TabsContent>
      </Tabs>

      <StudentFormDialog open={editOpen} onOpenChange={setEditOpen} student={student} />

      <Dialog open={!!statusTarget} onOpenChange={(open) => !open && setStatusTarget(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>
              Mark student as {statusTarget ? studentStatusLabels[statusTarget] : ""}
            </DialogTitle>
          </DialogHeader>
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
            <DialogTitle>Delete student</DialogTitle>
          </DialogHeader>
          <p className="text-sm text-muted-foreground">
            Are you sure you want to delete{" "}
            <span className="font-medium">{student.full_name}</span>? This action cannot be undone.
          </p>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDeleteOpen(false)}>
              Cancel
            </Button>
            <Button variant="destructive" onClick={handleDelete} disabled={deleteStudent.isPending}>
              {deleteStudent.isPending ? "Deleting..." : "Delete"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
