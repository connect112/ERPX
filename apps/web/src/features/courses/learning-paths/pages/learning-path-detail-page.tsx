import { ArrowLeft, Plus, Trash2 } from "lucide-react";
import { useState } from "react";
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
import { useCoursesList } from "@/features/courses/api/courses-hooks";
import {
  useAddCourseToPath,
  useLearningPath,
  usePathCourses,
  useRemoveCourseFromPath,
} from "@/features/courses/learning-paths/api/learning-paths-hooks";

export function LearningPathDetailPage() {
  const { pathId } = useParams<{ pathId: string }>();
  const navigate = useNavigate();
  const { data: path, isLoading } = useLearningPath(pathId);
  const { data: pathCourses } = usePathCourses(pathId ?? "");
  const { data: allCourses } = useCoursesList({ limit: 200 });
  const addCourse = useAddCourseToPath(pathId ?? "");
  const removeCourse = useRemoveCourseFromPath(pathId ?? "");

  const [formOpen, setFormOpen] = useState(false);
  const [selectedCourseId, setSelectedCourseId] = useState("");
  const [orderIndex, setOrderIndex] = useState("1");

  if (isLoading || !path) {
    return (
      <div className="space-y-4 p-8">
        <Skeleton className="h-8 w-64" />
        <Skeleton className="h-64 w-full" />
      </div>
    );
  }

  const courseTitle = (courseId: string) =>
    allCourses?.items.find((c) => c.id === courseId)?.title ?? courseId;

  const sortedPathCourses = [...(pathCourses ?? [])].sort((a, b) => a.order_index - b.order_index);

  const onAdd = () => {
    if (!selectedCourseId) return;
    addCourse.mutate(
      { course_id: selectedCourseId, order_index: Number(orderIndex) },
      {
        onSuccess: () => {
          setFormOpen(false);
          setSelectedCourseId("");
          setOrderIndex("1");
        },
      }
    );
  };

  return (
    <div className="space-y-6 p-8">
      <div className="flex items-center gap-3">
        <Button variant="ghost" size="icon" onClick={() => navigate("/courses/learning-paths")}>
          <ArrowLeft className="h-4 w-4" />
        </Button>
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">{path.title}</h1>
          <p className="text-xs text-muted-foreground">{path.slug}</p>
        </div>
      </div>

      {path.description && <p className="text-sm text-muted-foreground">{path.description}</p>}

      <Card>
        <CardHeader className="flex flex-row items-center justify-between space-y-0">
          <CardTitle className="text-base">Courses in this path</CardTitle>
          <Button size="sm" onClick={() => setFormOpen(true)}>
            <Plus className="h-4 w-4" />
            Add course
          </Button>
        </CardHeader>
        <CardContent className="space-y-2">
          {sortedPathCourses.length === 0 && (
            <p className="text-sm text-muted-foreground">
              No courses added yet. Add courses to define the learning sequence.
            </p>
          )}
          {sortedPathCourses.map((entry) => (
            <div key={entry.id} className="flex items-center justify-between rounded-md border p-3">
              <span className="text-sm font-medium">
                {entry.order_index}. {courseTitle(entry.course_id)}
              </span>
              <Button
                variant="ghost"
                size="icon"
                onClick={() => removeCourse.mutate(entry.course_id)}
              >
                <Trash2 className="h-4 w-4" />
              </Button>
            </div>
          ))}
        </CardContent>
      </Card>

      <Dialog open={formOpen} onOpenChange={setFormOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Add course to path</DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="course">Course</Label>
              <Select value={selectedCourseId || undefined} onValueChange={setSelectedCourseId}>
                <SelectTrigger id="course">
                  <SelectValue placeholder="Select a course" />
                </SelectTrigger>
                <SelectContent>
                  {allCourses?.items.map((c) => (
                    <SelectItem key={c.id} value={c.id}>
                      {c.title}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label htmlFor="orderIndex">Order</Label>
              <Input
                id="orderIndex"
                type="number"
                value={orderIndex}
                onChange={(e) => setOrderIndex(e.target.value)}
              />
            </div>
            {addCourse.isError && (
              <p className="text-sm text-destructive">
                {(addCourse.error as { response?: { data?: { error?: { message?: string } } } })
                  ?.response?.data?.error?.message ?? "Something went wrong. Please try again."}
              </p>
            )}
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setFormOpen(false)}>
              Cancel
            </Button>
            <Button onClick={onAdd} disabled={!selectedCourseId || addCourse.isPending}>
              {addCourse.isPending ? "Adding..." : "Add course"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
