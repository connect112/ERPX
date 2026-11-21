import { useQuery } from "@tanstack/react-query";
import { Download, ExternalLink } from "lucide-react";
import { useState } from "react";

import { apiClient } from "@/api/client";

interface LessonResource {
  id: string;
  title: string;
  resource_type: string;
  file_url: string;
  is_downloadable: boolean;
  is_upload: boolean;
  original_filename: string | null;
  size_bytes: number | null;
}

const base = (courseId: string, chapterId: string, lessonId: string) => `/courses/${courseId}/chapters/${chapterId}/lessons/${lessonId}/resources`;

function size(bytes: number | null): string {
  if (bytes == null) return "";
  return bytes < 1024 * 1024 ? `${Math.max(1, Math.round(bytes / 1024))} KB` : `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

/** The files and links attached to one lesson. An uploaded file is fetched through a short-lived link the server hands out only to a student with a live enrolment. */
export function LessonResources({ courseId, chapterId, lessonId }: { courseId: string; chapterId: string; lessonId: string }) {
  const [error, setError] = useState<string | null>(null);
  const resources = useQuery({
    queryKey: ["lesson-resources", courseId, chapterId, lessonId],
    queryFn: () => apiClient.get<LessonResource[]>(base(courseId, chapterId, lessonId)).then((r) => r.data),
  });
  if (!resources.data || resources.data.length === 0) return null;

  const download = async (id: string) => {
    setError(null);
    try {
      const { url } = await apiClient.get<{ url: string }>(`${base(courseId, chapterId, lessonId)}/${id}/download`).then((r) => r.data);
      window.open(url, "_blank", "noopener,noreferrer");
    } catch {
      setError("This file is not available to download.");
    }
  };

  return (
    <ul className="ml-6 mt-1 space-y-0.5" data-testid="lesson-resources">
      {resources.data.map((r) => (
        <li key={r.id} className="text-xs">
          {r.is_upload ? (
            r.is_downloadable ? (
              <button type="button" onClick={() => void download(r.id)} className="inline-flex items-center gap-1 text-primary hover:underline">
                <Download className="h-3 w-3" />
                {r.title} <span className="text-muted-foreground">({r.original_filename}, {size(r.size_bytes)})</span>
              </button>
            ) : (
              <span className="text-muted-foreground">{r.title} (view only)</span>
            )
          ) : (
            <a href={r.file_url} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 text-primary hover:underline">
              <ExternalLink className="h-3 w-3" />
              {r.title}
            </a>
          )}
        </li>
      ))}
      {error && <li className="text-destructive">{error}</li>}
    </ul>
  );
}
