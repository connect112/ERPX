import { Bookmark, BookmarkCheck, CheckCircle2, Circle } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { useMarkLessonComplete, useMyLessons } from "@/features/courses/api/courses-hooks";
import type { ChapterPublic } from "@/features/courses/api/courses-api";
import {
  useAddBookmark,
  useMyBookmarks,
  useRemoveBookmark,
} from "@/features/bookmarks/api/bookmarks-hooks";

interface ChapterLessonsProps {
  courseId: string;
  chapter: ChapterPublic;
  completedLessonIds: Set<string>;
}

export function ChapterLessons({ courseId, chapter, completedLessonIds }: ChapterLessonsProps) {
  const { data: lessons, isLoading } = useMyLessons(courseId, chapter.id);
  const markComplete = useMarkLessonComplete(courseId);
  const { data: bookmarks } = useMyBookmarks();
  const addBookmark = useAddBookmark();
  const removeBookmark = useRemoveBookmark();
  const bookmarkedLessonIds = new Set((bookmarks ?? []).map((b) => b.lesson_id));

  return (
    <div className="border-t px-4 py-3">
      <p className="mb-2 text-sm font-semibold">{chapter.title}</p>
      {isLoading ? (
        <Skeleton className="h-8 w-full" />
      ) : lessons && lessons.length > 0 ? (
        <ul className="space-y-1">
          {lessons.map((lesson) => {
            const isComplete = completedLessonIds.has(lesson.id);
            const isBookmarked = bookmarkedLessonIds.has(lesson.id);
            return (
              <li
                key={lesson.id}
                className="flex items-center justify-between rounded-md px-2 py-1.5 hover:bg-muted/50"
              >
                <div className="flex items-center gap-2">
                  {isComplete ? (
                    <CheckCircle2 className="h-4 w-4 text-primary" />
                  ) : (
                    <Circle className="h-4 w-4 text-muted-foreground" />
                  )}
                  <span className="text-sm">{lesson.title}</span>
                </div>
                <div className="flex items-center gap-1">
                  <Button
                    size="icon"
                    variant="ghost"
                    disabled={addBookmark.isPending || removeBookmark.isPending}
                    onClick={() =>
                      isBookmarked
                        ? removeBookmark.mutate(lesson.id)
                        : addBookmark.mutate(lesson.id)
                    }
                    aria-label={isBookmarked ? "Remove bookmark" : "Bookmark this lesson"}
                  >
                    {isBookmarked ? (
                      <BookmarkCheck className="h-4 w-4 text-primary" />
                    ) : (
                      <Bookmark className="h-4 w-4 text-muted-foreground" />
                    )}
                  </Button>
                  {!isComplete && (
                    <Button
                      size="sm"
                      variant="ghost"
                      disabled={markComplete.isPending}
                      onClick={() => markComplete.mutate(lesson.id)}
                    >
                      Mark complete
                    </Button>
                  )}
                </div>
              </li>
            );
          })}
        </ul>
      ) : (
        <p className="text-sm text-muted-foreground">No lessons in this chapter yet.</p>
      )}
    </div>
  );
}
