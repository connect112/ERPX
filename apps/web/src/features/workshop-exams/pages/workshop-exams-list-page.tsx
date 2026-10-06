import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Plus } from "lucide-react";
import { useState } from "react";
import { useNavigate } from "react-router-dom";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { workshopExamsApi } from "@/features/workshop-exams/api/workshop-exams-api";
import { examStatusBadge } from "@/features/workshop-exams/lib/status";

export function WorkshopExamsListPage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [formOpen, setFormOpen] = useState(false);
  const [title, setTitle] = useState("");
  const [duration, setDuration] = useState("30");

  const { data, isLoading, isError } = useQuery({
    queryKey: ["workshop-exams", "list"],
    queryFn: () => workshopExamsApi.list(),
  });

  const create = useMutation({
    mutationFn: () => workshopExamsApi.create({ title: title.trim(), duration_minutes: Number(duration) }),
    onSuccess: (exam) => {
      queryClient.invalidateQueries({ queryKey: ["workshop-exams"] });
      setFormOpen(false);
      setTitle("");
      navigate(`/workshop-exams/${exam.id}`);
    },
  });

  return (
    <div className="space-y-6 p-6">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold">Workshop Exams</h1>
          <p className="text-sm text-muted-foreground">
            Login-free MCQ exams for workshop attendees. Everyone who writes the exam gets a certificate by email
            at the time you choose.
          </p>
        </div>
        <Button onClick={() => setFormOpen(true)}>
          <Plus className="h-4 w-4" />
          New exam
        </Button>
      </div>

      <Card>
        <CardContent className="p-0">
          {isLoading ? (
            <div className="space-y-2 p-6">
              <Skeleton className="h-10 w-full" />
              <Skeleton className="h-10 w-full" />
            </div>
          ) : isError ? (
            <p className="p-6 text-sm text-destructive">Could not load exams.</p>
          ) : (data?.length ?? 0) === 0 ? (
            <p className="p-8 text-center text-sm text-muted-foreground">No workshop exams yet.</p>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Title</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Questions</TableHead>
                  <TableHead>Attendees</TableHead>
                  <TableHead>Duration</TableHead>
                  <TableHead>Certificates</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {data?.map((exam) => (
                  <TableRow
                    key={exam.id}
                    className="cursor-pointer"
                    onClick={() => navigate(`/workshop-exams/${exam.id}`)}
                  >
                    <TableCell className="font-medium">{exam.title}</TableCell>
                    <TableCell>
                      <Badge variant={examStatusBadge[exam.status].variant}>
                        {examStatusBadge[exam.status].label}
                      </Badge>
                    </TableCell>
                    <TableCell>{exam.question_count}</TableCell>
                    <TableCell>{exam.attendee_count}</TableCell>
                    <TableCell>{exam.duration_minutes} min</TableCell>
                    <TableCell className="text-muted-foreground">
                      {exam.certificates_dispatched_at
                        ? "Sent"
                        : exam.certificate_release_at
                          ? new Date(exam.certificate_release_at).toLocaleString()
                          : "Not scheduled"}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      <Dialog open={formOpen} onOpenChange={setFormOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>New workshop exam</DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="exam-title">Title</Label>
              <Input id="exam-title" value={title} onChange={(e) => setTitle(e.target.value)} />
            </div>
            <div className="space-y-2">
              <Label htmlFor="exam-duration">Time limit (minutes, from when each person starts)</Label>
              <Input
                id="exam-duration"
                type="number"
                min={1}
                max={480}
                value={duration}
                onChange={(e) => setDuration(e.target.value)}
              />
            </div>
            {create.isError && <p className="text-sm text-destructive">Could not create the exam.</p>}
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setFormOpen(false)}>
              Cancel
            </Button>
            <Button disabled={title.trim().length < 2 || create.isPending} onClick={() => create.mutate()}>
              {create.isPending ? "Creating..." : "Create"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
