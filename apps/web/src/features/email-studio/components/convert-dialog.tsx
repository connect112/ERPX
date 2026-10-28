import { useMutation, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, CheckCircle2 } from "lucide-react";
import { Suspense, lazy, useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";

import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { type EditorDoc, type TemplateOut, studioApi, studioKeys } from "@/features/email-studio/api/studio-api";
import type { VisualEditorHandle } from "@/features/email-studio/components/visual-editor";
import { type ConversionReport, compareFacts, factsOfDoc, factsOfHtml } from "@/features/email-studio/lib/convert";
import { brandTheme } from "@/features/email-studio/lib/studio";
import { errorMessage } from "@/features/institutions/lib/format";

const VisualEditor = lazy(() => import("@/features/email-studio/components/visual-editor"));

interface Converted {
  doc: EditorDoc;
  html: string;
  report: ConversionReport;
}

/**
 * Offers a React Email code template as a design in the visual editor. The code is built first; its email is loaded into the editor
 * (out of sight); what the editor kept is compared with what the email contained, and anything that did not make it is listed
 * before anything is created. The result is a NEW template: the code version is never changed.
 */
export function ConvertDialog({ template, source, onClose }: { template: TemplateOut; source: string; onClose: () => void }) {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const editor = useRef<VisualEditorHandle | null>(null);
  const [built, setBuilt] = useState<{ html: string } | { errors: string[] } | null>(null);
  const [converted, setConverted] = useState<Converted | null>(null);
  const [failed, setFailed] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    studioApi
      .reactBuild(source, template.current.preheader)
      .then((result) => {
        if (cancelled) return;
        setBuilt(result.ok ? { html: result.html } : { errors: result.errors.map((e) => (e.line ? `Line ${e.line}: ${e.message}` : e.message)) });
      })
      .catch((error) => !cancelled && setFailed(errorMessage(error, "Could not build the code.")));
    return () => {
      cancelled = true;
    };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [source, template.current.preheader]);

  // The editor loads the email asynchronously; take its design once it holds something.
  const html = built && "html" in built ? built.html : null;
  useEffect(() => {
    if (!html) return;
    let tries = 0;
    const timer = window.setInterval(async () => {
      tries += 1;
      try {
        const snap = await editor.current?.snapshot();
        if (snap && (snap.editor_json.content?.length ?? 0) > 0) {
          window.clearInterval(timer);
          setConverted({ doc: snap.editor_json, html: snap.html, report: compareFacts(factsOfHtml(html), factsOfDoc(snap.editor_json)) });
        }
      } catch {
        /* the editor is not ready yet */
      }
      if (tries > 25) {
        window.clearInterval(timer);
        setFailed("The visual editor could not read this email.");
      }
    }, 400);
    return () => window.clearInterval(timer);
  }, [html]);

  const create = useMutation({
    mutationFn: () => {
      if (!converted) throw new Error("Nothing to convert.");
      return studioApi.create({
        name: `${template.name} (visual)`.slice(0, 200),
        source_type: "visual",
        category: template.category,
        module: template.module,
        subject: template.current.subject,
        preheader: template.current.preheader,
        brand_profile_id: template.current.brand_profile_id,
        signature_id: template.current.signature_id,
        config: template.current.config ?? {},
        editor_json: converted.doc,
        html: converted.html,
      });
    },
    onSuccess: (created) => {
      void queryClient.invalidateQueries({ queryKey: studioKeys.library });
      navigate(`/administration/email-templates/studio/${created.id}`);
    },
  });

  return (
    <Dialog open onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="max-h-[90vh] max-w-xl overflow-y-auto">
        <DialogHeader>
          <DialogTitle>Convert to the visual editor</DialogTitle>
          <DialogDescription>
            Makes a design you can edit with the visual editor from this email. The code version stays as it is, in your library, to go back to.
          </DialogDescription>
        </DialogHeader>

        {failed && <p role="alert" className="text-sm text-destructive">{failed}</p>}
        {built && "errors" in built && (
          <div className="space-y-1 text-sm">
            <p className="font-medium text-destructive">The code has errors, so it cannot be converted yet.</p>
            <ul className="list-disc pl-5">
              {built.errors.slice(0, 6).map((e) => (
                <li key={e}>{e}</li>
              ))}
            </ul>
          </div>
        )}
        {!built && !failed && <p className="text-sm text-muted-foreground">Building the email...</p>}
        {html && !converted && !failed && <p className="text-sm text-muted-foreground" role="status">Reading it into the visual editor...</p>}

        {converted && (
          <div className="space-y-3 text-sm" data-testid="conversion-report">
            {converted.report.lost.length === 0 ? (
              <p className="flex items-start gap-2 text-emerald-700 dark:text-emerald-400">
                <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0" /> All of the text, links and images carried over.
              </p>
            ) : (
              <div className="space-y-1">
                <p className="flex items-center gap-2 font-medium text-amber-800 dark:text-amber-300">
                  <AlertTriangle className="h-4 w-4" /> Some things do not carry over
                </p>
                <ul className="list-disc space-y-1 pl-5">
                  {converted.report.lost.map((l) => (
                    <li key={l}>{l}</li>
                  ))}
                </ul>
                <p className="text-muted-foreground">You can add them back in the visual editor, or keep the code version, which has all of it.</p>
              </div>
            )}
            <ul className="list-disc space-y-1 pl-5 text-muted-foreground">
              {converted.report.notes.map((n) => (
                <li key={n}>{n}</li>
              ))}
            </ul>
          </div>
        )}
        {create.isError && <p role="alert" className="text-sm text-destructive">{errorMessage(create.error, "Could not create the design.")}</p>}

        <div className="flex flex-wrap justify-end gap-2">
          <Button variant="outline" onClick={onClose}>Cancel</Button>
          <Button disabled={!converted || create.isPending} onClick={() => create.mutate()}>
            {create.isPending ? "Creating..." : converted && converted.report.lost.length ? "Convert anyway" : "Create visual design"}
          </Button>
        </div>

        {html && (
          <div aria-hidden="true" className="pointer-events-none fixed -left-[10000px] top-0 w-[900px]">
            <Suspense fallback={null}>
              <VisualEditor ref={editor} content={html as unknown as EditorDoc} theme={brandTheme(null)} onChange={() => undefined} />
            </Suspense>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}
