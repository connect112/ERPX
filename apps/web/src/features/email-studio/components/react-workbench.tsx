import { useMutation } from "@tanstack/react-query";
import { AlertTriangle, CheckCircle2, Hammer, Redo2, Sparkles, Undo2, WandSparkles, XCircle } from "lucide-react";
import { Suspense, forwardRef, lazy, useCallback, useEffect, useRef, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { type DraftPayload, type ReactBuild, type ReactIssue, type SourceType, studioApi } from "@/features/email-studio/api/studio-api";
import { PreviewPane } from "@/features/email-studio/components/preview-pane";
import type { ReactEditorHandle } from "@/features/email-studio/components/react-editor";
import { BUILD_LABEL, REACT_EXAMPLE, buildState, formatReactSource } from "@/features/email-studio/lib/react-import";
import { errorMessage } from "@/features/institutions/lib/format";
import { cn } from "@/lib/utils";

const ReactEditor = lazy(() => import("@/features/email-studio/components/react-editor"));

interface Props {
  source: string;
  onSource: (value: string) => void;
  preheader: string;
  readOnly?: boolean;
  /** The draft as the server needs it to draw a preview (with react_source set to the code on screen). */
  getDraft: () => Promise<DraftPayload>;
  erpxKey: string | null;
  canUseStudents: boolean;
  /** Called after every build, so the page can fill in the subject and preview line from the code. */
  onBuilt?: (build: ReactBuild) => void;
  /** Offered when the code cannot be imported: the HTML tab on the create page. */
  onUseHtml?: () => void;
  /** Buttons for the page to add next to Validate & Build (Convert to Visual Editor...). */
  actions?: React.ReactNode;
  /** Fill the height of the parent instead of using fixed heights. */
  fill?: boolean;
  /** Build once when first shown (for an already-saved template). */
  autoBuild?: boolean;
  sourceType?: SourceType;
}

type Tab = "preview" | "problems";

/**
 * The React Email code editor with its build: Validate & Build reads the code on the server (it is never run), and the result is
 * shown as a status, a list of errors and warnings that point at their lines, and the final email as it will be sent.
 */
export const ReactWorkbench = forwardRef<ReactEditorHandle, Props>(function ReactWorkbench(
  { source, onSource, preheader, readOnly, getDraft, erpxKey, canUseStudents, onBuilt, onUseHtml, actions, fill, autoBuild, sourceType = "react" },
  ref,
) {
  const [build, setBuild] = useState<ReactBuild | null>(null);
  const [builtSource, setBuiltSource] = useState<string | null>(null);
  const [previewKey, setPreviewKey] = useState(0);
  const [tab, setTab] = useState<Tab>("preview");
  const [live, setLive] = useState(false);
  const [formatting, setFormatting] = useState(false);
  const [formatError, setFormatError] = useState<string | null>(null);
  const editor = useRef<ReactEditorHandle | null>(null);

  const run = useMutation({
    mutationFn: (text: string) => studioApi.reactBuild(text, preheader),
    onSuccess: (result, text) => {
      setBuild(result);
      setBuiltSource(text);
      setTab(result.ok ? "preview" : "problems");
      if (result.ok) setPreviewKey((n) => n + 1);
      onBuilt?.(result);
    },
  });
  const trigger = run.mutate;

  const doBuild = useCallback(() => trigger(source), [trigger, source]);

  useEffect(() => {
    if (autoBuild && source.trim()) trigger(source);
    // only once, when the workbench first appears
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (!live || !source.trim() || source === builtSource) return;
    const timer = window.setTimeout(() => trigger(source), 900);
    return () => window.clearTimeout(timer);
  }, [live, source, builtSource, trigger]);

  const state = buildState(build, run.isPending, builtSource, source);
  const label = BUILD_LABEL[state];
  const issues: ReactIssue[] = build && builtSource === source ? [...build.errors, ...build.warnings] : [];

  const format = async () => {
    setFormatting(true);
    setFormatError(null);
    try {
      onSource(await formatReactSource(source));
    } catch (error) {
      setFormatError(error instanceof Error ? error.message.split("\n")[0] : "Could not format the code.");
    } finally {
      setFormatting(false);
    }
  };

  const setHandle = (handle: ReactEditorHandle | null) => {
    editor.current = handle;
    if (typeof ref === "function") ref(handle);
    else if (ref) (ref as React.MutableRefObject<ReactEditorHandle | null>).current = handle;
  };

  return (
    <div className={cn("flex flex-col gap-2", fill && "xl:h-full xl:min-h-0")}>
      <div className="flex flex-wrap items-center gap-2 xl:shrink-0">
        <Button disabled={readOnly || run.isPending || !source.trim()} onClick={doBuild}>
          <Hammer className="h-4 w-4" /> {run.isPending ? "Building..." : "Validate & Build"}
        </Button>
        <Button variant="outline" size="sm" disabled={readOnly || formatting || !source.trim()} onClick={() => void format()}>
          <WandSparkles className="h-4 w-4" /> {formatting ? "Formatting..." : "Format code"}
        </Button>
        <Button variant="ghost" size="icon" aria-label="Undo" disabled={readOnly} onClick={() => editor.current?.undo()}>
          <Undo2 className="h-4 w-4" />
        </Button>
        <Button variant="ghost" size="icon" aria-label="Redo" disabled={readOnly} onClick={() => editor.current?.redo()}>
          <Redo2 className="h-4 w-4" />
        </Button>
        {!source.trim() && !readOnly && (
          <Button variant="ghost" size="sm" onClick={() => onSource(REACT_EXAMPLE)}>
            <Sparkles className="h-4 w-4" /> Load an example
          </Button>
        )}
        <label className="flex items-center gap-1.5 text-xs text-muted-foreground">
          <input type="checkbox" checked={live} onChange={(e) => setLive(e.target.checked)} /> Build as I type
        </label>
        <div className="ml-auto flex flex-wrap items-center gap-2">
          {actions}
          <Badge variant={label.tone} role="status" aria-live="polite" data-testid="build-status">
            {label.label}
            {state === "ok" && build ? ` · ${build.warnings.length} warning${build.warnings.length === 1 ? "" : "s"}` : ""}
            {state === "errors" && build ? ` · ${build.errors.length} error${build.errors.length === 1 ? "" : "s"}` : ""}
          </Badge>
        </div>
      </div>
      {formatError && <p role="alert" className="text-xs text-destructive">Could not format: {formatError}. Fix the syntax errors first.</p>}

      <div className={cn("grid gap-2 2xl:grid-cols-2", fill && "xl:min-h-0 xl:flex-1 xl:grid-rows-[minmax(0,3fr)_minmax(0,2fr)] 2xl:grid-rows-1")}>
        <div className={cn("h-[55vh] min-h-[380px] min-w-0", fill && "xl:h-auto xl:min-h-[240px]")}>
          <Suspense fallback={<Skeleton className="h-full min-h-[320px] w-full" />}>
            <ReactEditor ref={setHandle} value={source} onChange={onSource} issues={issues} readOnly={readOnly} height="100%" minHeight="200px" />
          </Suspense>
        </div>

        <section className={cn("flex h-[70vh] min-h-[380px] min-w-0 flex-col rounded-md border", fill && "xl:h-auto xl:min-h-[240px]")} aria-label="Build result">
          <div className="flex shrink-0 items-center gap-1 border-b p-1" role="tablist">
            <Button role="tab" aria-selected={tab === "preview"} size="sm" variant={tab === "preview" ? "default" : "ghost"} onClick={() => setTab("preview")}>
              Rendered preview
            </Button>
            <Button role="tab" aria-selected={tab === "problems"} size="sm" variant={tab === "problems" ? "default" : "ghost"} onClick={() => setTab("problems")}>
              Errors & warnings
              {build && (build.errors.length > 0 || build.warnings.length > 0) && (
                <span className={cn("ml-1 rounded-full px-1.5 text-[10px]", build.errors.length ? "bg-destructive text-destructive-foreground" : "bg-amber-500/20")}>
                  {build.errors.length + build.warnings.length}
                </span>
              )}
            </Button>
          </div>
          <div className="min-h-0 flex-1 overflow-y-auto p-3">
            {tab === "preview" &&
              (source.trim() ? (
                state === "errors" ? (
                  <p className="text-sm text-muted-foreground">The code has errors, so there is nothing to show yet. See "Errors & warnings".</p>
                ) : (
                  <PreviewPane sourceType={sourceType} getDraft={getDraft} erpxKey={erpxKey} canUseStudents={canUseStudents} refreshKey={previewKey} compact />
                )
              ) : (
                <p className="text-sm text-muted-foreground">Paste React Email code on the left, then choose Validate & Build to see the email here.</p>
              ))}
            {tab === "problems" && <Problems build={build} stale={state === "stale"} error={run.isError ? errorMessage(run.error, "Could not check the code.") : null} onGo={(line) => editor.current?.goToLine(line)} onUseHtml={onUseHtml} />}
          </div>
        </section>
      </div>
    </div>
  );
});

function Problems({ build, stale, error, onGo, onUseHtml }: { build: ReactBuild | null; stale: boolean; error: string | null; onGo: (line: number) => void; onUseHtml?: () => void }) {
  if (error) return <p role="alert" className="text-sm text-destructive">{error}</p>;
  if (!build) return <p className="text-sm text-muted-foreground">Nothing has been checked yet. Choose Validate & Build.</p>;
  const nothing = build.errors.length === 0 && build.warnings.length === 0 && build.unsupported_placeholders.length === 0;
  return (
    <div className="space-y-3 text-sm">
      {stale && <p className="rounded-md bg-amber-500/10 p-2 text-xs text-amber-800 dark:text-amber-300">The code changed after this check. Build again to refresh it.</p>}
      {build.ok && (
        <p className="flex items-center gap-2 text-emerald-700 dark:text-emerald-400">
          <CheckCircle2 className="h-4 w-4" /> The code was read successfully{build.components.length ? ` (${build.components.join(", ")})` : ""}.
        </p>
      )}
      {nothing && build.ok && <p className="text-muted-foreground">No warnings.</p>}
      {build.errors.length > 0 && (
        <div className="space-y-2">
          <p className="font-medium text-destructive">This code cannot be imported as it is</p>
          <IssueList issues={build.errors} onGo={onGo} />
          <p className="rounded-md border p-2 text-xs text-muted-foreground">
            Nothing here is ever run, so code that needs a library, another file, a network call or logic cannot be imported. Fix the lines above, or take the finished email from
            the source (react.email lets you copy the HTML) and use the HTML tab instead.
            {onUseHtml && (
              <>
                {" "}
                <button type="button" className="underline" onClick={onUseHtml}>Open the HTML tab</button>
              </>
            )}
          </p>
        </div>
      )}
      {build.unsupported_placeholders.length > 0 && (
        <p className="flex items-start gap-2 text-amber-800 dark:text-amber-300">
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
          <span>These placeholders do not exist in ERPX and would stay empty: {build.unsupported_placeholders.map((n) => `{{${n}}}`).join(", ")}. Pick them from the Placeholders list.</span>
        </p>
      )}
      {build.warnings.length > 0 && (
        <div className="space-y-2">
          <p className="font-medium">Changed or left out ({build.warnings.length})</p>
          <IssueList issues={build.warnings} onGo={onGo} />
        </div>
      )}
    </div>
  );
}

function IssueList({ issues, onGo }: { issues: ReactIssue[]; onGo: (line: number) => void }) {
  return (
    <ul className="space-y-1.5">
      {issues.map((i, n) => (
        <li key={`${i.line}-${n}`} className="flex items-start gap-2 rounded-md border p-2">
          {i.severity === "error" ? <XCircle className="mt-0.5 h-4 w-4 shrink-0 text-destructive" /> : <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-amber-600" />}
          <div className="min-w-0 flex-1">
            {i.line ? (
              <button type="button" className="mr-2 rounded bg-muted px-1.5 py-0.5 font-mono text-xs underline-offset-2 hover:underline" onClick={() => onGo(i.line as number)}>
                Line {i.line}
              </button>
            ) : null}
            <span className="break-words">{i.message}</span>
          </div>
        </li>
      ))}
    </ul>
  );
}

export default ReactWorkbench;
