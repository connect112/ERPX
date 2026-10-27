import { useMutation, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, Download, RefreshCw } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { errorMessage } from "@/features/institutions/lib/format";
import { type LetterConfig, type LetterSettings, letterKeys, lettersApi, useLetterStudents } from "@/features/our-internships/api/letters-api";
import { selectClass } from "@/features/our-internships/components/letter-fields";
import { DESIGN_TEXT, safeFileName, saveBlob } from "@/features/our-internships/lib/letters";

/**
 * The letter as it will be made, for one student or a sample, from the settings on screen (saved or not). Refresh draws it
 * again after a change. Approving is a separate, deliberate step: letters can only be generated from an approved design,
 * and any later change to the settings undoes the approval.
 */
export function LettersPreview({ internshipId, settings, draft, dirty }: { internshipId: string; settings: LetterSettings; draft: LetterConfig; dirty: boolean }) {
  const queryClient = useQueryClient();
  const students = useLetterStudents(internshipId);
  const [studentId, setStudentId] = useState<string>("");
  const [url, setUrl] = useState<string | null>(null);
  const urlRef = useRef<string | null>(null);
  const [info, setInfo] = useState<{ pages: number; sample: boolean } | null>(null);

  const render = useMutation({
    mutationFn: () => lettersApi.preview(internshipId, studentId || null, draft),
    onSuccess: ({ blob, pages, sample }) => {
      setInfo({ pages, sample });
      if (urlRef.current) URL.revokeObjectURL(urlRef.current);
      urlRef.current = URL.createObjectURL(new Blob([blob], { type: "application/pdf" }));
      setUrl(urlRef.current);
    },
  });
  const draw = render.mutate;
  // draw once when the tab opens and again whenever another student is chosen; edits are drawn when Refresh is pressed
  useEffect(() => {
    draw();
  }, [studentId, draw]);
  useEffect(
    () => () => {
      if (urlRef.current) URL.revokeObjectURL(urlRef.current);
    },
    [],
  );

  const approve = useMutation({
    mutationFn: () => lettersApi.approveDesign(internshipId),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: letterKeys.all(internshipId) }),
  });
  const download = useCallback(async () => {
    const { blob } = await lettersApi.preview(internshipId, studentId || null, draft);
    const name = students.data?.students.find((s) => s.student_id === studentId)?.name ?? "Sample";
    saveBlob(blob, `OfferLetter_Preview_${safeFileName(name)}.pdf`);
  }, [internshipId, studentId, draft, students.data]);

  const state = settings.design_state;
  return (
    <div className="space-y-4">
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Preview and approve the design</CardTitle>
          <CardDescription>Check both pages for a real student. Change the settings on the Configuration tab, then Refresh.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="flex flex-wrap items-end gap-3">
            <div className="space-y-1.5">
              <label htmlFor="pv-student" className="text-sm font-medium">
                Student
              </label>
              <select id="pv-student" className={`${selectClass} min-w-[16rem]`} value={studentId} onChange={(e) => setStudentId(e.target.value)}>
                <option value="">A sample student</option>
                {students.data?.students.map((s) => (
                  <option key={s.student_id} value={s.student_id}>
                    {s.name}
                    {s.issues.length ? " (details missing)" : ""}
                  </option>
                ))}
              </select>
            </div>
            <Button variant="outline" disabled={render.isPending} onClick={() => draw()}>
              <RefreshCw className={`h-4 w-4 ${render.isPending ? "animate-spin" : ""}`} />
              Refresh preview
            </Button>
            <Button variant="outline" disabled={!url} onClick={() => void download()}>
              <Download className="h-4 w-4" />
              Download this preview
            </Button>
            {info && (
              <span className="text-sm text-muted-foreground">
                {info.pages} page{info.pages === 1 ? "" : "s"}
                {info.sample ? " · sample details" : ""}
              </span>
            )}
          </div>
          {dirty && <p className="text-sm text-amber-700 dark:text-amber-400">The preview shows your unsaved changes. Save them on the Configuration tab before approving.</p>}
          {render.isError && <p className="text-sm text-destructive">{errorMessage(render.error, "Could not draw the preview.")}</p>}
        </CardContent>
      </Card>

      <div className="rounded-md border bg-muted/30">
        {url ? <iframe title="Offer letter preview" src={url} className="h-[80vh] w-full rounded-md" /> : <Skeleton className="h-[60vh] w-full" />}
      </div>

      <Card>
        <CardContent className="flex flex-wrap items-center justify-between gap-3 pt-6">
          <div className="space-y-1">
            <div className="flex items-center gap-2">
              <Badge variant={state === "approved" ? "success" : state === "changed" ? "warning" : "secondary"}>{state === "approved" ? "Approved" : state === "changed" ? "Needs approval again" : "Not approved"}</Badge>
              <span className="text-sm">{DESIGN_TEXT[state]}</span>
            </div>
            {settings.problems.length > 0 && <p className="text-sm text-amber-700 dark:text-amber-400">Finish the settings first: {settings.problems.join(" ")}</p>}
            {approve.isError && <p className="text-sm text-destructive">{errorMessage(approve.error, "Could not approve.")}</p>}
          </div>
          <Button disabled={state === "approved" || dirty || settings.problems.length > 0 || approve.isPending} onClick={() => approve.mutate()}>
            <CheckCircle2 className="h-4 w-4" />
            {approve.isPending ? "Approving..." : "Approve this design"}
          </Button>
        </CardContent>
      </Card>
    </div>
  );
}
