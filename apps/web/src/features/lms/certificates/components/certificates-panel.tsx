import { Award, Plus } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { useCoursesList } from "@/features/courses/api/courses-hooks";
import { useEnrollmentsForStudent } from "@/features/lms/enrollment/api/enrollment-hooks";
import {
  useCertificatesForStudent,
  useIssueCertificate,
} from "@/features/lms/certificates/api/certificates-hooks";

export function CertificatesPanel({ studentId }: { studentId: string }) {
  const { data: certificates, isLoading } = useCertificatesForStudent(studentId);
  const { data: enrollments } = useEnrollmentsForStudent(studentId);
  const { data: courses } = useCoursesList({ limit: 200 });
  const issueCertificate = useIssueCertificate(studentId);

  const [formOpen, setFormOpen] = useState(false);
  const [selectedCourse, setSelectedCourse] = useState("");
  const [force, setForce] = useState(false);

  const courseTitle = (id: string) => courses?.items.find((c) => c.id === id)?.title ?? id;
  const eligibleCourses = enrollments?.filter((e) => e.status !== "dropped") ?? [];

  const onIssue = () => {
    if (!selectedCourse) return;
    issueCertificate.mutate(
      { courseId: selectedCourse, force },
      {
        onSuccess: () => {
          setFormOpen(false);
          setSelectedCourse("");
          setForce(false);
        },
      }
    );
  };

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between space-y-0">
        <CardTitle className="text-base">Certificates</CardTitle>
        <Button size="sm" onClick={() => setFormOpen(true)}>
          <Plus className="h-4 w-4" />
          Issue certificate
        </Button>
      </CardHeader>
      <CardContent className="space-y-2">
        {isLoading && <Skeleton className="h-12 w-full" />}
        {!isLoading && (certificates?.length ?? 0) === 0 && (
          <p className="text-sm text-muted-foreground">No certificates issued yet.</p>
        )}
        {certificates?.map((cert) => (
          <div key={cert.id} className="flex items-center justify-between rounded-md border p-3">
            <div className="flex items-center gap-2">
              <Award className="h-4 w-4 text-primary" />
              <div>
                <p className="text-sm font-medium">{courseTitle(cert.course_id)}</p>
                <p className="text-xs text-muted-foreground">{cert.certificate_number}</p>
              </div>
            </div>
            <p className="text-xs text-muted-foreground">
              {new Date(cert.issued_at).toLocaleDateString()}
            </p>
          </div>
        ))}
      </CardContent>

      <Dialog open={formOpen} onOpenChange={setFormOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Issue certificate</DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="course">Course</Label>
              <Select value={selectedCourse || undefined} onValueChange={setSelectedCourse}>
                <SelectTrigger id="course">
                  <SelectValue placeholder="Select a course" />
                </SelectTrigger>
                <SelectContent>
                  {eligibleCourses.map((e) => (
                    <SelectItem key={e.course_id} value={e.course_id}>
                      {courseTitle(e.course_id)}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <label className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                className="h-4 w-4 rounded border-input"
                checked={force}
                onChange={(e) => setForce(e.target.checked)}
              />
              Force issue (bypass 100% completion requirement)
            </label>
            {issueCertificate.isError && (
              <p className="text-sm text-destructive">
                {(issueCertificate.error as { response?: { data?: { error?: { message?: string } } } })
                  ?.response?.data?.error?.message ?? "Something went wrong. Please try again."}
              </p>
            )}
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setFormOpen(false)}>
              Cancel
            </Button>
            <Button onClick={onIssue} disabled={!selectedCourse || issueCertificate.isPending}>
              {issueCertificate.isPending ? "Issuing..." : "Issue certificate"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </Card>
  );
}
