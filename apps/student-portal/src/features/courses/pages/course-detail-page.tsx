import { useParams } from "react-router-dom";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { ChapterLessons } from "@/features/courses/components/chapter-lessons";
import {
  useMyChapters,
  useMyCourse,
  useMyCourseProgress,
} from "@/features/courses/api/courses-hooks";

export function CourseDetailPage() {
  const { courseId } = useParams<{ courseId: string }>();

  const { data: course, isLoading: courseLoading } = useMyCourse(courseId);
  const { data: chapters, isLoading: chaptersLoading } = useMyChapters(courseId);
  const { data: progress, isLoading: progressLoading } = useMyCourseProgress(courseId);

  const completedLessonIds = new Set(progress?.completed_lesson_ids ?? []);

  return (
    <div className="space-y-6 p-6">
      <div>
        {courseLoading ? (
          <Skeleton className="h-8 w-80" />
        ) : (
          <h1 className="text-2xl font-semibold">{course?.title}</h1>
        )}
        {course?.short_description && (
          <p className="text-sm text-muted-foreground">{course.short_description}</p>
        )}
      </div>

      <Card>
        <CardHeader className="pb-2">
          <CardDescription>Your progress</CardDescription>
          {progressLoading ? (
            <Skeleton className="h-6 w-40" />
          ) : (
            <CardTitle className="text-lg">
              {progress?.completed_lessons} / {progress?.total_lessons} lessons complete
            </CardTitle>
          )}
        </CardHeader>
        <CardContent>
          <div className="h-2 w-full overflow-hidden rounded-full bg-muted">
            <div
              className="h-full rounded-full bg-primary transition-all"
              style={{ width: `${progress?.percent_complete ?? 0}%` }}
            />
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Chapters</CardTitle>
          <CardDescription>Work through each chapter and mark lessons complete.</CardDescription>
        </CardHeader>
        <CardContent className="p-0">
          {chaptersLoading ? (
            <div className="space-y-2 p-6">
              <Skeleton className="h-10 w-full" />
              <Skeleton className="h-10 w-full" />
            </div>
          ) : chapters && chapters.length > 0 ? (
            chapters
              .sort((a, b) => a.order_index - b.order_index)
              .map((chapter) => (
                <ChapterLessons
                  key={chapter.id}
                  courseId={courseId as string}
                  chapter={chapter}
                  completedLessonIds={completedLessonIds}
                />
              ))
          ) : (
            <p className="p-6 text-center text-sm text-muted-foreground">
              This course has no chapters yet.
            </p>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
