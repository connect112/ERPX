import { useMutation, useQuery } from "@tanstack/react-query";
import { Monitor, RefreshCw, Smartphone } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { errorMessage } from "@/features/institutions/lib/format";
import { type DraftPayload, type PreviewContext, type SourceType, studioApi } from "@/features/email-studio/api/studio-api";
import { selectClass } from "@/features/our-internships/components/letter-fields";
import { ourInternshipsApi } from "@/features/our-internships/api/our-internships-api";

type View = "rendered" | "text" | "source";

/**
 * The email as it will arrive, drawn by the server from the draft on screen (saved or not). The HTML is shown in a sandboxed frame
 * with scripts disabled, so even a template full of unsafe markup cannot run anything here. Nothing is sent from a preview.
 */
export function PreviewPane({
  sourceType,
  getDraft,
  erpxKey,
  canUseStudents,
  refreshKey,
}: {
  sourceType: SourceType;
  getDraft: () => Promise<DraftPayload>;
  erpxKey: string | null;
  canUseStudents: boolean;
  refreshKey: number;
}) {
  const [device, setDevice] = useState<"desktop" | "mobile">("desktop");
  const [view, setView] = useState<View>("rendered");
  const [internshipId, setInternshipId] = useState("");
  const [studentId, setStudentId] = useState("");

  const internships = useQuery({ queryKey: ["email-studio", "preview-internships"], queryFn: ourInternshipsApi.list, enabled: canUseStudents });
  const students = useQuery({
    queryKey: ["email-studio", "preview-students", internshipId],
    queryFn: () => ourInternshipsApi.selected(internshipId),
    enabled: canUseStudents && !!internshipId,
  });

  const context: PreviewContext = useMemo(
    () => (internshipId && studentId ? { type: "internship", key: erpxKey, internship_id: internshipId, student_id: studentId } : { type: "sample", key: erpxKey }),
    [internshipId, studentId, erpxKey],
  );
  const render = useMutation({ mutationFn: async () => studioApi.preview(sourceType, await getDraft(), context) });
  const draw = render.mutate;
  useEffect(() => {
    draw();
  }, [draw, context, refreshKey]);

  const result = render.data;
  const problems = [
    ...(result?.missing.length ? [`No value for ${result.missing.map((n) => `{{${n}}}`).join(", ")} with this data.`] : []),
    ...(result?.unsupported.length ? [`Not available here: ${result.unsupported.map((n) => `{{${n}}}`).join(", ")}.`] : []),
    ...(result?.warnings ?? []),
  ];

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-end gap-3">
        <div className="inline-flex rounded-md border p-0.5" role="group" aria-label="Preview size">
          <Button size="sm" variant={device === "desktop" ? "default" : "ghost"} onClick={() => setDevice("desktop")} aria-pressed={device === "desktop"}>
            <Monitor className="h-4 w-4" /> Desktop
          </Button>
          <Button size="sm" variant={device === "mobile" ? "default" : "ghost"} onClick={() => setDevice("mobile")} aria-pressed={device === "mobile"}>
            <Smartphone className="h-4 w-4" /> Mobile
          </Button>
        </div>
        <div className="inline-flex rounded-md border p-0.5" role="group" aria-label="Preview as">
          {(["rendered", "text", "source"] as View[]).map((v) => (
            <Button key={v} size="sm" variant={view === v ? "default" : "ghost"} onClick={() => setView(v)} aria-pressed={view === v}>
              {v === "rendered" ? "Email" : v === "text" ? "Plain text" : "HTML"}
            </Button>
          ))}
        </div>
        {canUseStudents && (
          <>
            <div className="space-y-1">
              <label htmlFor="pv-internship" className="text-xs font-medium">Internship</label>
              <select id="pv-internship" className={`${selectClass} w-48`} value={internshipId} onChange={(e) => { setInternshipId(e.target.value); setStudentId(""); }}>
                <option value="">Sample recipient</option>
                {internships.data?.map((i) => (
                  <option key={i.id} value={i.id}>
                    {i.title}
                  </option>
                ))}
              </select>
            </div>
            {internshipId && (
              <div className="space-y-1">
                <label htmlFor="pv-student" className="text-xs font-medium">Student</label>
                <select id="pv-student" className={`${selectClass} w-48`} value={studentId} onChange={(e) => setStudentId(e.target.value)}>
                  <option value="">Choose a student</option>
                  {students.data?.items.map((s) => (
                    <option key={s.student_id} value={s.student_id}>
                      {s.name}
                    </option>
                  ))}
                </select>
              </div>
            )}
          </>
        )}
        <Button size="sm" variant="outline" disabled={render.isPending} onClick={() => draw()}>
          <RefreshCw className={`h-4 w-4 ${render.isPending ? "animate-spin" : ""}`} /> Refresh
        </Button>
      </div>

      {render.isError && <p className="text-sm text-destructive">{errorMessage(render.error, "Could not draw the preview.")}</p>}
      {result && (
        <div className="space-y-1 rounded-md border p-3 text-sm">
          <p>
            <span className="text-muted-foreground">Subject:</span> <strong>{result.subject || "(empty)"}</strong>
          </p>
          {result.attachments.length > 0 && (
            <div className="flex flex-wrap items-center gap-1">
              <span className="text-muted-foreground">Attachments:</span>
              {result.attachments.map((a, i) => (
                <Badge key={i} variant="secondary">
                  {a.kind === "recipient" ? `Recipient's ${a.name ?? "document"}${a.required ? " (required)" : ""}` : (a.name ?? "Shared file")}
                </Badge>
              ))}
            </div>
          )}
          {problems.length > 0 && (
            <ul className="list-disc pl-5 text-amber-700 dark:text-amber-400">
              {problems.map((p) => (
                <li key={p}>{p}</li>
              ))}
            </ul>
          )}
        </div>
      )}

      {!result ? (
        <Skeleton className="h-[60vh] w-full" />
      ) : view === "rendered" ? (
        <div className="overflow-x-auto rounded-md border bg-muted/40 p-3">
          <iframe
            title="Email preview"
            sandbox=""
            srcDoc={result.html}
            style={{ width: device === "mobile" ? 375 : 680, maxWidth: "100%" }}
            className="mx-auto block h-[62vh] rounded border bg-white"
          />
        </div>
      ) : (
        <pre className="max-h-[62vh] overflow-auto whitespace-pre-wrap rounded-md border bg-muted/40 p-3 text-xs">{view === "text" ? result.text : result.html}</pre>
      )}
    </div>
  );
}
