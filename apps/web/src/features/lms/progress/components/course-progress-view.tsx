import { useState } from "react";

import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { useChapters } from "@/features/courses/chapters/api/chapters-hooks";
import { useLessons } from "@/features/courses/lessons/api/lessons-hooks";
import { useCourseProgress, useToggleLessonProgress } from "@/features/lms/progress/api/progress-hooks";

function LessonPicker({
  courseId,
  chapterId,
  lessonId,
  onLessonChange,
}: {
  courseId: string;
  chapterId: string;
  lessonId: string;
  onLessonChange: (id: string) => void;
}) {
  const { data: lessons } = useLessons(courseId, chapterId);
  return (
    <Select value={lessonId || undefined} onValueChange={onLessonChange}>
      <SelectTrigger className="w-56">
        <SelectValue placeholder="Select a lesson" />
      </SelectTrigger>
      <SelectContent>
        {lessons?.map((lesson) => (
          <SelectItem key={lesson.id} value={lesson.id}>
            {lesson.title}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  );
}

export function CourseProgressView({ studentId, courseId }: { studentId: string; courseId: string }) {
  const { data: progress, isLoading } = useCourseProgress(studentId, courseId);
  const { data: chapters } = useChapters(courseId);
  const toggleLesson = useToggleLessonProgress(studentId, courseId);

  const [chapterId, setChapterId] = useState("");
  const [lessonId, setLessonId] = useState("");

  const percent = progress?.percent_complete ?? 0;

  return (
    <div className="space-y-3">
      {!isLoading && progress && (
        <div>
          <div className="flex items-center justify-between text-xs text-muted-foreground">
            <span>
              {progress.completed_lessons} / {progress.total_lessons} lessons
            </span>
            <span>{percent.toFixed(0)}%</span>
          </div>
          <div className="mt-1 h-2 w-full overflow-hidden rounded-full bg-muted">
            <div
              className="h-full rounded-full bg-primary transition-all"
              style={{ width: `${Math.min(100, Math.max(0, percent))}%` }}
            />
          </div>
        </div>
      )}

      <div className="flex flex-wrap items-center gap-2">
        <Select
          value={chapterId || undefined}
          onValueChange={(value) => {
            setChapterId(value);
            setLessonId("");
          }}
        >
          <SelectTrigger className="w-56">
            <SelectValue placeholder="Select a chapter" />
          </SelectTrigger>
          <SelectContent>
            {chapters?.map((chapter) => (
              <SelectItem key={chapter.id} value={chapter.id}>
                {chapter.title}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>

        {chapterId && (
          <LessonPicker
            courseId={courseId}
            chapterId={chapterId}
            lessonId={lessonId}
            onLessonChange={setLessonId}
          />
        )}

        <Button
          size="sm"
          variant="outline"
          disabled={!lessonId || toggleLesson.isPending}
          onClick={() => toggleLesson.mutate({ lessonId, complete: true })}
        >
          Mark complete
        </Button>
        <Button
          size="sm"
          variant="ghost"
          disabled={!lessonId || toggleLesson.isPending}
          onClick={() => toggleLesson.mutate({ lessonId, complete: false })}
        >
          Mark incomplete
        </Button>
      </div>
    </div>
  );
}
