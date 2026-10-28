import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useParams } from "react-router-dom";

import { Skeleton } from "@/components/ui/skeleton";
import { type TemplateOut, studioKeys, useTemplate } from "@/features/email-studio/api/studio-api";
import { EditorWorkspace } from "@/features/email-studio/components/editor-workspace";
import { errorMessage } from "@/features/institutions/lib/format";

/** The editor, full width. A restore or discard remounts it so it starts from the version it now holds. */
export function EditorPage() {
  const { templateId = "" } = useParams();
  const queryClient = useQueryClient();
  const template = useTemplate(templateId);
  const [remount, setRemount] = useState(0);

  if (template.isLoading) return <div className="p-8"><Skeleton className="h-[70vh] w-full" /></div>;
  if (template.isError || !template.data) {
    return <p className="p-8 text-sm text-destructive">{errorMessage(template.error, "Could not open this template.")}</p>;
  }
  return (
    <div className="p-6">
      <EditorWorkspace
        key={`${templateId}-${remount}`}
        template={template.data}
        onTemplate={(t: TemplateOut, again: boolean) => {
          queryClient.setQueryData(studioKeys.template(templateId), t);
          if (again) setRemount((n) => n + 1);
        }}
      />
    </div>
  );
}
