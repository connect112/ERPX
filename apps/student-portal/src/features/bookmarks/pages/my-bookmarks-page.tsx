import { Bookmark, Trash2 } from "lucide-react";
import { Link } from "react-router-dom";

import { Skeleton } from "@/components/ui/skeleton";
import { Button } from "@/components/ui/button";
import { useMyBookmarks, useRemoveBookmark } from "@/features/bookmarks/api/bookmarks-hooks";

export function MyBookmarksPage() {
  const { data, isLoading, isError } = useMyBookmarks();
  const removeBookmark = useRemoveBookmark();

  return (
    <div className="space-y-6 p-8">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">My Bookmarks</h1>
        <p className="mt-1 text-muted-foreground">Lessons you've saved for later.</p>
      </div>

      {isLoading && (
        <div className="space-y-2">
          {Array.from({ length: 3 }).map((_, i) => (
            <Skeleton key={i} className="h-14 w-full" />
          ))}
        </div>
      )}

      {isError && <p className="text-sm text-destructive">Failed to load bookmarks.</p>}

      {!isLoading && !isError && (data?.length ?? 0) === 0 && (
        <p className="py-8 text-center text-sm text-muted-foreground">
          No bookmarks yet. Bookmark a lesson from any course to save it here.
        </p>
      )}

      {!isLoading && !isError && (data?.length ?? 0) > 0 && (
        <ul className="divide-y rounded-lg border bg-card">
          {data?.map((bookmark) => (
            <li key={bookmark.id} className="flex items-center justify-between px-4 py-3">
              <div className="flex items-center gap-3">
                <Bookmark className="h-4 w-4 text-primary" />
                <div>
                  <Link
                    to={`/courses/${bookmark.course_id}`}
                    className="text-sm font-medium hover:underline"
                  >
                    {bookmark.lesson_title}
                  </Link>
                  <p className="text-xs text-muted-foreground">{bookmark.course_title}</p>
                </div>
              </div>
              <Button
                variant="ghost"
                size="icon"
                onClick={() => removeBookmark.mutate(bookmark.lesson_id)}
                aria-label={`Remove bookmark for ${bookmark.lesson_title}`}
              >
                <Trash2 className="h-4 w-4" />
              </Button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
