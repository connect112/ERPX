import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, Eye, PanelRight, Redo2, Repeat2, Save, Send, Undo2, Upload, Trash2, Plus } from "lucide-react";
import { Suspense, lazy, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { Textarea } from "@/components/ui/textarea";
import {
  type Attachment,
  type CodeTemplate,
  type DraftPayload,
  type TemplateOut,
  studioApi,
  studioKeys,
  useBrands,
  useCodeTemplates,
  useLibrary,
  useSignatures,
} from "@/features/email-studio/api/studio-api";
import { CodePropsForm } from "@/features/email-studio/components/code-props-form";
import { ConvertDialog } from "@/features/email-studio/components/convert-dialog";
import { DeleteTemplateDialog } from "@/features/email-studio/components/delete-template-dialog";
import type { HtmlEditorHandle } from "@/features/email-studio/components/html-editor";
import { PlaceholderPicker } from "@/features/email-studio/components/placeholder-picker";
import { PreviewPane } from "@/features/email-studio/components/preview-pane";
import type { ReactEditorHandle } from "@/features/email-studio/components/react-editor";
import { ReactWorkbench } from "@/features/email-studio/components/react-workbench";
import { TestDialog } from "@/features/email-studio/components/test-dialog";
import type { VisualEditorHandle } from "@/features/email-studio/components/visual-editor";
import { STATUS_LABEL, brandTheme, token } from "@/features/email-studio/lib/studio";
import { useStudioPermissions } from "@/features/email-studio/lib/permissions";
import { errorMessage } from "@/features/institutions/lib/format";
import { selectClass } from "@/features/our-internships/components/letter-fields";

const VisualEditor = lazy(() => import("@/features/email-studio/components/visual-editor"));
const HtmlEditor = lazy(() => import("@/features/email-studio/components/html-editor"));

type Panel = "email" | "placeholders" | "versions" | "use";

/**
 * Where one email is designed. The design lives in this component's state until Save draft; Publish saves it first and then makes it
 * the version real emails use. Insert buttons type into whichever field (subject, design or HTML) had the cursor last.
 */
export function EditorWorkspace({ template, onTemplate, initialNotice }: { template: TemplateOut; onTemplate: (t: TemplateOut, remount: boolean) => void; initialNotice?: string | null }) {
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const perms = useStudioPermissions();
  const brands = useBrands();
  const signatures = useSignatures();
  const codeTemplates = useCodeTemplates();
  const categories = useQuery({ queryKey: ["email-studio", "categories"], queryFn: studioApi.categories, staleTime: Infinity });

  const cur = template.current;
  const [name, setName] = useState(template.name);
  const [description, setDescription] = useState(template.description);
  const [category, setCategory] = useState(template.category);
  const [subject, setSubject] = useState(cur.subject);
  const [preheader, setPreheader] = useState(cur.preheader);
  const [brandId, setBrandId] = useState<string | null>(cur.brand_profile_id);
  const [signatureId, setSignatureId] = useState<string | null>(cur.signature_id);
  const [config, setConfig] = useState(cur.config ?? {});
  const [codeProps, setCodeProps] = useState<Record<string, string>>(cur.code_props ?? {});
  const [html, setHtml] = useState(cur.html_source ?? cur.body_html);
  const [source, setSource] = useState(cur.react_source ?? "");
  const [dirty, setDirty] = useState(false);
  const [deleteOpen, setDeleteOpen] = useState(false);
  const [convertOpen, setConvertOpen] = useState(false);
  const [settingsOpen, setSettingsOpen] = useState(true);
  const [panel, setPanel] = useState<Panel>("email");
  const [previewOpen, setPreviewOpen] = useState(false);
  const [testOpen, setTestOpen] = useState(false);
  const [previewKey, setPreviewKey] = useState(0);
  const [notice, setNotice] = useState<string | null>(initialNotice ?? null);
  const [, redraw] = useState(0);

  const visual = useRef<VisualEditorHandle | null>(null);
  const htmlEditor = useRef<HtmlEditorHandle | null>(null);
  const reactEditor = useRef<ReactEditorHandle | null>(null);
  const subjectInput = useRef<HTMLInputElement | null>(null);
  const inserter = useRef<(text: string) => void>(() => undefined);

  const brand = useMemo(() => brands.data?.find((b) => b.id === brandId) ?? brands.data?.find((b) => b.is_default) ?? null, [brands.data, brandId]);
  const code: CodeTemplate | undefined = codeTemplates.data?.find((c) => c.key === cur.code_template_key);
  const erpxKey = template.assignments.find((a) => !a.hackathon_id)?.key ?? code?.suggested_for ?? null;
  const edit = <T,>(setter: (v: T) => void) => (v: T) => {
    setter(v);
    setDirty(true);
  };

  useEffect(() => {
    const warn = (e: BeforeUnloadEvent) => {
      if (dirty) e.preventDefault();
    };
    window.addEventListener("beforeunload", warn);
    return () => window.removeEventListener("beforeunload", warn);
  }, [dirty]);

  /** What is on screen, as the server wants it. */
  const getDraft = useCallback(async (): Promise<DraftPayload> => {
    const base: DraftPayload = { name, description, category, subject, preheader, brand_profile_id: brandId, signature_id: signatureId, config };
    if (template.source_type === "visual") {
      const snap = await visual.current?.snapshot();
      return snap ? { ...base, editor_json: snap.editor_json, html: snap.html } : { ...base, editor_json: cur.editor_json, html: cur.body_html };
    }
    if (template.source_type === "html") return { ...base, html };
    if (template.source_type === "react") return { ...base, react_source: source };
    return { ...base, code_template_key: cur.code_template_key, code_props: codeProps };
  }, [name, description, category, subject, preheader, brandId, signatureId, config, html, source, codeProps, template.source_type, cur]);

  const done = (t: TemplateOut, remount = false) => {
    onTemplate(t, remount);
    void queryClient.invalidateQueries({ queryKey: studioKeys.library });
    void queryClient.invalidateQueries({ queryKey: studioKeys.versions(t.id) });
  };

  const save = useMutation({
    mutationFn: async () => studioApi.saveDraft(template.id, await getDraft()),
    onSuccess: (t) => {
      setDirty(false);
      setNotice("Draft saved. Nothing that is sent has changed until you publish.");
      done(t);
    },
  });
  const publish = useMutation({
    mutationFn: async () => {
      await studioApi.saveDraft(template.id, await getDraft());
      return studioApi.publish(template.id);
    },
    onSuccess: (t) => {
      setDirty(false);
      setNotice(
        t.assignments.length
          ? `Published as version ${t.published_version_number}. It is now used for: ${t.assignments.map((a) => a.name).join(", ")}.`
          : `Published as version ${t.published_version_number}. It is not used for any ERPX email until you choose one under "Use for".`,
      );
      done(t);
    },
  });
  const discard = useMutation({ mutationFn: () => studioApi.discardDraft(template.id), onSuccess: (t) => done(t, true) });
  const remove = useMutation({
    mutationFn: () => studioApi.remove(template.id),
    onSuccess: () => {
      setDirty(false);
      void queryClient.invalidateQueries({ queryKey: studioKeys.library });
      navigate("/administration/email-templates");
    },
  });
  const restore = useMutation({ mutationFn: (versionId: string) => studioApi.restore(template.id, versionId), onSuccess: (t) => done(t, true) });
  const versions = useQuery({ queryKey: studioKeys.versions(template.id), queryFn: () => studioApi.versions(template.id), enabled: panel === "versions" });

  const archived = template.status === "archived";
  const readOnly = !perms.canManage || archived;
  const status = STATUS_LABEL[template.status];

  const insert = (text: string) => inserter.current(text);
  const focusSubject = () => {
    inserter.current = (text) => {
      const el = subjectInput.current;
      if (!el) return;
      const start = el.selectionStart ?? el.value.length;
      const end = el.selectionEnd ?? start;
      const next = el.value.slice(0, start) + text + el.value.slice(end);
      edit(setSubject)(next);
      requestAnimationFrame(() => {
        el.focus();
        el.setSelectionRange(start + text.length, start + text.length);
      });
    };
  };
  useEffect(() => {
    // by default, placeholders go into the design (or the HTML)
    inserter.current = (text) =>
      template.source_type === "visual" ? visual.current?.insertText(text) : template.source_type === "react" ? reactEditor.current?.insertText(text) : htmlEditor.current?.insertText(text);
  }, [template.source_type]);

  const attachments = config.attachments ?? [];
  const setAttachments = (next: Attachment[]) => edit(setConfig)({ ...config, attachments: next });

  return (
    <div className="space-y-4 xl:flex xl:min-h-0 xl:flex-1 xl:flex-col xl:space-y-0 xl:gap-3">
      <div className="sticky top-0 z-20 -mx-6 -mt-6 flex flex-wrap items-center gap-3 border-b bg-background px-6 py-3 xl:static xl:z-auto xl:mx-0 xl:mt-0 xl:shrink-0 xl:border-0 xl:p-0" role="toolbar" aria-label="Email actions">
        <Link to="/administration/email-templates" className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground">
          <ArrowLeft className="h-4 w-4" /> Back to Library
        </Link>
        <Input aria-label="Template name" className="h-9 max-w-xs font-medium" value={name} disabled={readOnly} onChange={(e) => edit(setName)(e.target.value)} />
        <Badge variant={status.variant}>{status.label}</Badge>
        <span className="text-xs text-muted-foreground">
          {template.has_draft ? `Draft v${cur.version_number}` : `Version ${cur.version_number}`}
          {template.published_version_number ? ` · published v${template.published_version_number}` : ""}
          {dirty ? " · unsaved changes" : ""}
        </span>
        <div className="ml-auto flex flex-wrap items-center gap-2">
          {template.source_type === "visual" && (
            <>
              <Button size="icon" variant="ghost" aria-label="Undo" disabled={readOnly || !visual.current?.canUndo()} onClick={() => { visual.current?.undo(); redraw((n) => n + 1); }}>
                <Undo2 className="h-4 w-4" />
              </Button>
              <Button size="icon" variant="ghost" aria-label="Redo" disabled={readOnly || !visual.current?.canRedo()} onClick={() => { visual.current?.redo(); redraw((n) => n + 1); }}>
                <Redo2 className="h-4 w-4" />
              </Button>
            </>
          )}
          <Button variant="outline" onClick={() => { setPreviewKey((n) => n + 1); setPreviewOpen(true); }}>
            <Eye className="h-4 w-4" /> Preview
          </Button>
          <Button variant="outline" size="icon" className="xl:hidden" aria-label={settingsOpen ? "Hide email settings" : "Show email settings"} aria-expanded={settingsOpen} onClick={() => setSettingsOpen((open) => !open)}>
            <PanelRight className="h-4 w-4" />
          </Button>
          <Button
            variant="outline"
            size="icon"
            aria-label="Delete this template"
            title="Delete this template"
            disabled={!perms.canManage || template.is_system}
            onClick={() => setDeleteOpen(true)}
          >
            <Trash2 className="h-4 w-4 text-destructive" />
          </Button>
          <Button variant="outline" disabled={!perms.canManage} onClick={() => setTestOpen(true)}>
            <Send className="h-4 w-4" /> Send test
          </Button>
          <Button variant="outline" disabled={readOnly || save.isPending || !dirty} onClick={() => save.mutate()}>
            <Save className="h-4 w-4" /> {save.isPending ? "Saving..." : "Save draft"}
          </Button>
          <Button
            disabled={!perms.canPublish || archived || publish.isPending || (!dirty && !template.has_draft)}
            title={perms.canPublish ? undefined : "You need permission to publish email templates"}
            onClick={() => {
              if (window.confirm("Publish this version? Emails that use this template will use it from now on.")) publish.mutate();
            }}
          >
            {publish.isPending ? "Publishing..." : "Publish"}
          </Button>
        </div>
      </div>
      {archived && <p className="rounded-md border p-3 text-sm text-muted-foreground">This template is archived. Restore it from the library to edit it.</p>}
      {(save.isError || publish.isError || discard.isError || restore.isError) && (
        <p role="alert" className="text-sm text-destructive xl:shrink-0">
          {errorMessage(save.error ?? publish.error ?? discard.error ?? restore.error, "Could not do that.")}
        </p>
      )}
      {notice && !dirty && <p role="status" className="text-sm text-emerald-700 dark:text-emerald-400">{notice}</p>}

      <div className="grid gap-4 xl:min-h-0 xl:flex-1 xl:grid-cols-[minmax(0,1fr)_22rem] xl:grid-rows-[minmax(0,1fr)]">
        <div className="min-w-0 xl:min-h-0 xl:overflow-y-auto">
          {template.source_type === "visual" && (
            <Suspense fallback={<Skeleton className="h-[60vh] w-full" />}>
              <div className="xl:h-full" onFocusCapture={() => { inserter.current = (text) => visual.current?.insertText(text); }}>
                <VisualEditor ref={visual} content={cur.editor_json} theme={brandTheme(brand)} onChange={() => !readOnly && setDirty(true)} />
              </div>
            </Suspense>
          )}
          {template.source_type === "html" && (
            <div onFocusCapture={() => { inserter.current = (text) => htmlEditor.current?.insertText(text); }}>
              <Suspense fallback={<Skeleton className="h-[60vh] w-full" />}>
                <HtmlEditor ref={htmlEditor} value={html} onChange={(v) => !readOnly && edit(setHtml)(v)} />
              </Suspense>
              <p className="mt-2 text-xs text-muted-foreground">
                Paste or edit the HTML. The original is kept as written; the version that is sent has scripts, forms, frames, risky links and risky styles removed.
                {" "}A shared header, footer or signature is only added where you place {"{{brand_header}}"}, {"{{brand_footer}}"} or {"{{signature}}"}.
              </p>
            </div>
          )}
          {template.source_type === "react" && (
            <div className="xl:h-full" onFocusCapture={() => { inserter.current = (text) => reactEditor.current?.insertText(text); }}>
              <ReactWorkbench
                ref={reactEditor}
                fill
                autoBuild
                source={source}
                onSource={(v) => !readOnly && edit(setSource)(v)}
                preheader={preheader}
                readOnly={readOnly}
                getDraft={getDraft}
                erpxKey={erpxKey}
                canUseStudents={perms.canUseStudents}
                onBuilt={(b) => {
                  if (b.ok && !preheader.trim() && b.preheader) edit(setPreheader)(b.preheader);
                }}
                actions={
                  <Button variant="outline" size="sm" disabled={!perms.canManage || !source.trim()} onClick={() => setConvertOpen(true)}>
                    <Repeat2 className="h-4 w-4" /> Convert to Visual Editor
                  </Button>
                }
              />
            </div>
          )}
          {template.source_type === "code" && code && <CodePropsForm template={code} values={codeProps} onChange={edit(setCodeProps)} />}
          {template.source_type === "code" && !code && <p className="text-sm text-destructive">This approved template is no longer available.</p>}
        </div>

        <aside className={`min-w-0 space-y-3 rounded-md border p-3 xl:block xl:min-h-0 xl:overflow-y-auto ${settingsOpen ? "" : "hidden"}`} aria-label="Email settings">
          <div className="flex flex-wrap gap-1" role="tablist">
            {([["email", "Email"], ["placeholders", "Placeholders"], ["versions", "Versions"], ["use", "Use for"]] as [Panel, string][]).map(([id, label]) => (
              <Button key={id} role="tab" aria-selected={panel === id} size="sm" variant={panel === id ? "default" : "ghost"} onClick={() => setPanel(id)}>
                {label}
              </Button>
            ))}
          </div>

          {panel === "email" && (
            <div className="space-y-4">
              <div className="space-y-1.5">
                <Label htmlFor="es-subject">Subject</Label>
                <Input id="es-subject" ref={subjectInput} value={subject} disabled={readOnly} maxLength={300} onFocus={focusSubject} onChange={(e) => edit(setSubject)(e.target.value)} />
                <p className="text-xs text-muted-foreground">One line. Placeholders work here too; the preview shows the final subject.</p>
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="es-pre">Preview text</Label>
                <Input id="es-pre" value={preheader} disabled={readOnly} maxLength={200} onChange={(e) => edit(setPreheader)(e.target.value)} />
                <p className="text-xs text-muted-foreground">The grey line many inboxes show after the subject.</p>
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="es-brand">Brand profile</Label>
                <select id="es-brand" className={selectClass} value={brandId ?? ""} disabled={readOnly} onChange={(e) => edit(setBrandId)(e.target.value || null)}>
                  <option value="">Default brand{brands.data?.find((b) => b.is_default) ? ` (${brands.data.find((b) => b.is_default)?.name})` : ""}</option>
                  {brands.data?.map((b) => (
                    <option key={b.id} value={b.id}>{b.name}</option>
                  ))}
                </select>
                <p className="text-xs text-muted-foreground">Its colours style the design; insert {token("brand_header")} and {token("brand_footer")} to place its header and footer.</p>
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="es-sig">Signature</Label>
                <select id="es-sig" className={selectClass} value={signatureId ?? ""} disabled={readOnly} onChange={(e) => edit(setSignatureId)(e.target.value || null)}>
                  <option value="">No signature</option>
                  {signatures.data?.map((s) => (
                    <option key={s.id} value={s.id}>{s.name}</option>
                  ))}
                </select>
                {template.source_type === "react" && signatureId && (
                  <p className="text-xs text-muted-foreground">Imported code keeps its own sign-off. The signature appears only where the code has {token("signature")}.</p>
                )}
                {template.source_type === "visual" && signatureId && (
                  <label className="flex items-center gap-2 text-xs">
                    <input type="checkbox" checked={config.auto_signature ?? true} disabled={readOnly} onChange={(e) => edit(setConfig)({ ...config, auto_signature: e.target.checked })} />
                    Add it at the end unless I place {token("signature")} myself
                  </label>
                )}
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="es-cat">Category</Label>
                <select id="es-cat" className={selectClass} value={category} disabled={readOnly} onChange={(e) => edit(setCategory)(e.target.value)}>
                  {categories.data?.map((c) => (
                    <option key={c} value={c}>{c}</option>
                  ))}
                </select>
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="es-desc">Description</Label>
                <Textarea id="es-desc" rows={2} value={description} disabled={readOnly} maxLength={500} onChange={(e) => edit(setDescription)(e.target.value)} />
              </div>
              <fieldset className="space-y-2" disabled={readOnly}>
                <legend className="text-sm font-medium">Attachments</legend>
                <p className="text-xs text-muted-foreground">
                  A student's own document (offer letter, certificate) is made and attached by its ERPX module; marking it here makes the preview show it and sending refuse to go without it.
                </p>
                {attachments.map((a, i) => (
                  <div key={i} className="flex items-center gap-2 text-sm">
                    <Badge variant="secondary">{a.kind === "recipient" ? "Recipient's" : "Shared"}</Badge>
                    <span className="min-w-0 flex-1 truncate">{a.name ?? a.asset}</span>
                    {a.kind === "recipient" && (
                      <label className="flex items-center gap-1 text-xs">
                        <input type="checkbox" checked={!!a.required} onChange={(e) => setAttachments(attachments.map((x, j) => (j === i ? { ...x, required: e.target.checked } : x)))} /> required
                      </label>
                    )}
                    <Button size="icon" variant="ghost" aria-label={`Remove attachment ${a.name ?? ""}`} onClick={() => setAttachments(attachments.filter((_, j) => j !== i))}>
                      <Trash2 className="h-3.5 w-3.5" />
                    </Button>
                  </div>
                ))}
                <div className="flex flex-wrap gap-2">
                  {["Offer letter", "Certificate", "Payslip"].map((n) => (
                    <Button key={n} type="button" size="sm" variant="outline" disabled={attachments.some((a) => a.kind === "recipient" && a.name === n)} onClick={() => setAttachments([...attachments, { kind: "recipient", name: n, required: true }])}>
                      <Plus className="h-3.5 w-3.5" /> {n}
                    </Button>
                  ))}
                  <label className="inline-flex cursor-pointer items-center gap-1 rounded-md border px-2 py-1 text-xs hover:bg-muted">
                    <Upload className="h-3.5 w-3.5" /> Shared PDF
                    <input
                      type="file"
                      accept="application/pdf,.pdf"
                      className="sr-only"
                      onChange={async (e) => {
                        const file = e.target.files?.[0];
                        e.target.value = "";
                        if (!file) return;
                        try {
                          const asset = await studioApi.uploadAsset(file, "attachment");
                          setAttachments([...attachments, { kind: "shared", asset: asset.id, name: asset.filename }]);
                        } catch (error) {
                          setNotice(errorMessage(error, "Could not upload that file."));
                        }
                      }}
                    />
                  </label>
                </div>
              </fieldset>
            </div>
          )}

          {panel === "placeholders" && <PlaceholderPicker erpxKey={erpxKey} onInsert={insert} />}

          {panel === "versions" && (
            <div className="space-y-2">
              {template.has_draft && template.published_version_id && (
                <Button size="sm" variant="outline" disabled={readOnly || discard.isPending} onClick={() => { if (window.confirm("Throw away the draft and go back to the published version?")) discard.mutate(); }}>
                  Discard the draft
                </Button>
              )}
              {versions.isLoading && <Skeleton className="h-20 w-full" />}
              <ul className="space-y-2">
                {versions.data?.map((v) => (
                  <li key={v.id} className="rounded-md border p-2 text-sm">
                    <div className="flex items-center justify-between gap-2">
                      <div className="flex items-center gap-2 font-medium">
                        Version {v.version_number}
                        <Badge variant={v.state === "published" ? "success" : v.state === "draft" ? "warning" : "secondary"}>{v.state}</Badge>
                      </div>
                      <Button size="sm" variant="outline" disabled={readOnly || restore.isPending || v.state === "draft"} onClick={() => { if (window.confirm(`Use version ${v.version_number} as the draft? It is not sent until you publish it.`)) restore.mutate(v.id); }}>
                        Restore
                      </Button>
                    </div>
                    <p className="truncate text-xs text-muted-foreground">{v.subject}</p>
                    <p className="text-xs text-muted-foreground">
                      {v.published_at ? `Published ${new Date(v.published_at).toLocaleString()}${v.published_by_name ? ` by ${v.published_by_name}` : ""}` : `Edited ${new Date(v.created_at).toLocaleString()}${v.created_by_name ? ` by ${v.created_by_name}` : ""}`}
                    </p>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {panel === "use" && <UseFor template={template} dirty={dirty} suggested={code?.suggested_for ?? null} onChanged={(t) => done(t)} canPublish={perms.canPublish} />}
        </aside>
      </div>

      <Dialog open={previewOpen} onOpenChange={setPreviewOpen}>
        <DialogContent className="max-h-[92vh] max-w-5xl overflow-y-auto">
          <DialogHeader>
            <DialogTitle>Preview</DialogTitle>
            <DialogDescription>Drawn by the server from what is on screen, with sample data or a selected student's. Nothing is sent.</DialogDescription>
          </DialogHeader>
          {previewOpen && <PreviewPane sourceType={template.source_type} getDraft={getDraft} erpxKey={erpxKey} canUseStudents={perms.canUseStudents} refreshKey={previewKey} />}
        </DialogContent>
      </Dialog>
      {testOpen && <TestDialog sourceType={template.source_type} templateId={template.id} getDraft={getDraft} erpxKey={erpxKey} onClose={() => setTestOpen(false)} />}
      {convertOpen && <ConvertDialog template={template} source={source} onClose={() => setConvertOpen(false)} />}
      {deleteOpen && (
        <DeleteTemplateDialog
          name={template.name}
          usedBy={template.assignments.map((a) => a.name)}
          isSystem={template.is_system}
          pending={remove.isPending}
          error={remove.isError ? errorMessage(remove.error, "Could not delete the template.") : null}
          onConfirm={() => remove.mutate()}
          onClose={() => setDeleteOpen(false)}
          onReassign={() => {
            setDeleteOpen(false);
            setSettingsOpen(true);
            setPanel("use");
          }}
        />
      )}
    </div>
  );
}

/** Which ERPX email (verification, offer letter, certificate...) this template is used for. Choosing one is a separate, deliberate step. */
function UseFor({ template, dirty, suggested, onChanged, canPublish }: { template: TemplateOut; dirty: boolean; suggested: string | null; onChanged: (t: TemplateOut) => void; canPublish: boolean }) {
  const library = useLibrary();
  const [key, setKey] = useState(suggested ?? "");
  const system = (library.data ?? []).filter((i) => i.is_system && i.key);
  const assign = useMutation({
    mutationFn: async () => {
      await studioApi.assign(key, template.id);
      return studioApi.get(template.id);
    },
    onSuccess: onChanged,
  });
  const unassign = useMutation({
    mutationFn: async (k: string) => {
      await studioApi.unassign(k);
      return studioApi.get(template.id);
    },
    onSuccess: onChanged,
  });
  const published = template.status === "published" && !!template.published_version_id;

  return (
    <div className="space-y-3 text-sm">
      <p className="text-muted-foreground">
        A template only changes a real ERPX email when you choose it here. It uses the <strong>published</strong> version; drafts are never sent. Taking it off goes back to the previous wording.
      </p>
      {template.assignments.length > 0 && (
        <ul className="space-y-1">
          {template.assignments.map((a) => (
            <li key={`${a.key}-${a.hackathon_id}`} className="flex items-center justify-between gap-2 rounded-md border p-2">
              <span>{a.name}</span>
              <Button size="sm" variant="outline" disabled={!canPublish || unassign.isPending} onClick={() => { if (window.confirm(`Stop using this template for "${a.name}"?`)) unassign.mutate(a.key); }}>
                Stop using
              </Button>
            </li>
          ))}
        </ul>
      )}
      {!published && <p className="text-amber-700 dark:text-amber-400">Publish the template first.</p>}
      {dirty && <p className="text-amber-700 dark:text-amber-400">You have unsaved changes; the published version is used, not these.</p>}
      <div className="space-y-1.5">
        <Label htmlFor="es-use">ERPX email</Label>
        <select id="es-use" className={selectClass} value={key} onChange={(e) => setKey(e.target.value)}>
          <option value="">Choose an email...</option>
          {system.map((i) => (
            <option key={i.key} value={i.key ?? ""}>{i.name}</option>
          ))}
        </select>
      </div>
      {assign.isError && <p role="alert" className="text-destructive">{errorMessage(assign.error, "Could not use this template.")}</p>}
      <Button disabled={!key || !published || !canPublish || assign.isPending} onClick={() => { if (window.confirm("Use this template for that ERPX email from now on?")) assign.mutate(); }}>
        Use for this email
      </Button>
      {!canPublish && <p className="text-xs text-muted-foreground">You need permission to publish email templates.</p>}
    </div>
  );
}
