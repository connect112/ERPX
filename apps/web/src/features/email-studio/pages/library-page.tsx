import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Archive, ArchiveRestore, Copy, Eye, Mail, Paperclip, Pencil, Plus, Send, Trash2, Wand2 } from "lucide-react";
import { useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { type LibraryItem, type TemplateOut, studioApi, studioKeys, useCodeTemplates, useLibrary } from "@/features/email-studio/api/studio-api";
import { PreviewPane } from "@/features/email-studio/components/preview-pane";
import { useStudioPermissions } from "@/features/email-studio/lib/permissions";
import { type LibraryFilters, STATUS_LABEL, draftPayload, filterLibrary, groupByCategory } from "@/features/email-studio/lib/studio";
import { TemplateEditorDialog } from "@/features/email-templates/components/template-editor";
import { errorMessage } from "@/features/institutions/lib/format";
import { selectClass } from "@/features/our-internships/components/letter-fields";
import { useAuthStore } from "@/store/auth-store";

const METHODS = [
  { value: "visual", label: "Visual editor" },
  { value: "html", label: "HTML import" },
  { value: "code", label: "React Email component" },
  { value: "markdown", label: "Markdown (built-in)" },
  { value: "default", label: "Built-in" },
];

/** Every email in one list: the ones designed in Email Studio and the built-in ones ERPX has always sent. */
export function LibraryPage() {
  const library = useLibrary();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const perms = useStudioPermissions();
  const codeTemplates = useCodeTemplates();
  const [filters, setFilters] = useState<LibraryFilters>({ q: "", category: "", status: "", method: "", sort: "category" });
  const [legacyKey, setLegacyKey] = useState<string | null>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const [test, setTest] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const items = useMemo(() => library.data ?? [], [library.data]);
  const categories = useMemo(() => [...new Set(items.map((i) => i.category))].sort(), [items]);
  const shown = useMemo(() => filterLibrary(items, filters), [items, filters]);
  const refresh = () => queryClient.invalidateQueries({ queryKey: studioKeys.library });

  const act = useMutation({
    mutationFn: async (job: () => Promise<TemplateOut | void>) => job(),
    onSuccess: (result) => {
      void refresh();
      if (result && "current" in result && result.source_type) navigate(`/administration/email-templates/studio/${result.id}`);
    },
    onError: (e) => setError(errorMessage(e, "Could not do that.")),
  });

  /** A built-in email redesigned in the studio: from the approved component written for it, or a blank design. */
  const designInStudio = (item: LibraryItem) =>
    act.mutate(async () => {
      const code = codeTemplates.data?.find((c) => c.suggested_for === item.key);
      if (code) {
        return studioApi.create({ name: `${item.name} (Studio)`, source_type: "code", category: item.category, code_template_key: code.key, subject: code.subject, preheader: "", brand_profile_id: null, signature_id: null, config: {}, code_props: {} });
      }
      return studioApi.create({ name: `${item.name} (Studio)`, source_type: "visual", category: item.category, subject: "", preheader: "", brand_profile_id: null, signature_id: null, config: {}, editor_json: { type: "doc", content: [{ type: "paragraph" }] } });
    });

  if (library.isLoading) return <Skeleton className="h-64 w-full" />;
  if (library.isError) return <p className="text-sm text-destructive">Could not load the library.</p>;

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-end gap-3">
        <div className="space-y-1">
          <Label htmlFor="lib-q">Search</Label>
          <Input id="lib-q" className="w-56" placeholder="Name, description or module" value={filters.q} onChange={(e) => setFilters({ ...filters, q: e.target.value })} />
        </div>
        <div className="space-y-1">
          <Label htmlFor="lib-cat">Category</Label>
          <select id="lib-cat" className={`${selectClass} w-52`} value={filters.category} onChange={(e) => setFilters({ ...filters, category: e.target.value })}>
            <option value="">All categories</option>
            {categories.map((c) => (
              <option key={c} value={c}>{c}</option>
            ))}
          </select>
        </div>
        <div className="space-y-1">
          <Label htmlFor="lib-status">Status</Label>
          <select id="lib-status" className={`${selectClass} w-36`} value={filters.status} onChange={(e) => setFilters({ ...filters, status: e.target.value })}>
            <option value="">Any</option>
            <option value="active">Active (built-in)</option>
            <option value="draft">Draft</option>
            <option value="published">Published</option>
            <option value="archived">Archived</option>
          </select>
        </div>
        <div className="space-y-1">
          <Label htmlFor="lib-method">Created with</Label>
          <select id="lib-method" className={`${selectClass} w-48`} value={filters.method} onChange={(e) => setFilters({ ...filters, method: e.target.value })}>
            <option value="">Any</option>
            {METHODS.map((m) => (
              <option key={m.value} value={m.value}>{m.label}</option>
            ))}
          </select>
        </div>
        <div className="space-y-1">
          <Label htmlFor="lib-sort">Sort by</Label>
          <select id="lib-sort" className={`${selectClass} w-36`} value={filters.sort} onChange={(e) => setFilters({ ...filters, sort: e.target.value as LibraryFilters["sort"] })}>
            <option value="category">Category</option>
            <option value="name">Name</option>
            <option value="updated">Last updated</option>
          </select>
        </div>
        <Button asChild className="ml-auto">
          <Link to="/administration/email-templates/create">
            <Plus className="h-4 w-4" /> Create email
          </Link>
        </Button>
      </div>
      {error && <p role="alert" className="text-sm text-destructive">{error}</p>}
      {shown.length === 0 && <p className="rounded-md border p-8 text-center text-sm text-muted-foreground">No email matches these filters.</p>}

      {groupByCategory(shown).map(([category, rows]) => (
        <Card key={category}>
          <CardHeader>
            <CardTitle className="text-base">{category}</CardTitle>
            <CardDescription>
              {rows.length} email{rows.length === 1 ? "" : "s"}
            </CardDescription>
          </CardHeader>
          <CardContent className="p-0">
            <ul className="divide-y">
              {rows.map((row) => {
                const status = STATUS_LABEL[row.status];
                return (
                  <li key={row.id} className="flex flex-wrap items-start justify-between gap-3 px-6 py-4">
                    <div className="min-w-0 flex-1">
                      <div className="flex flex-wrap items-center gap-2 font-medium">
                        <Mail className="h-4 w-4 text-muted-foreground" aria-hidden="true" />
                        {row.is_system ? row.name : <Link className="hover:underline" to={`/administration/email-templates/studio/${row.id}`}>{row.name}</Link>}
                        {row.has_attachment && <Paperclip className="h-3.5 w-3.5 text-muted-foreground" aria-label="Has an attachment" />}
                        <Badge variant={status.variant}>{status.label}</Badge>
                        {row.has_draft && row.status === "published" && <Badge variant="warning">Unpublished changes</Badge>}
                        <Badge variant="outline">{row.creation_method}</Badge>
                      </div>
                      <p className="text-sm text-muted-foreground">{row.description || "No description."}</p>
                      <p className="text-xs text-muted-foreground">
                        {row.module ? `Module: ${row.module} · ` : ""}
                        {row.is_system && row.assigned_to.length > 0 ? "Uses a Studio template · " : ""}
                        {!row.is_system && row.assigned_to.length > 0 ? `Used for: ${row.assigned_to.join(", ")} · ` : ""}
                        {row.updated_at ? `Updated ${new Date(row.updated_at).toLocaleDateString()}${row.updated_by_name ? ` by ${row.updated_by_name}` : ""}` : "Never edited"}
                      </p>
                    </div>
                    <div className="flex flex-wrap items-center gap-1">
                      {row.is_system ? (
                        <>
                          <Button size="sm" variant="outline" onClick={() => setLegacyKey(row.key)}>
                            <Pencil className="h-4 w-4" /> Edit wording
                          </Button>
                          <Button size="sm" variant="outline" disabled={!perms.canManage || act.isPending} onClick={() => designInStudio(row)}>
                            <Wand2 className="h-4 w-4" /> Design in Studio
                          </Button>
                        </>
                      ) : (
                        <>
                          <Button size="sm" variant="outline" asChild>
                            <Link to={`/administration/email-templates/studio/${row.id}`}>
                              <Pencil className="h-4 w-4" /> {row.status === "archived" ? "Open" : "Edit"}
                            </Link>
                          </Button>
                          <Button size="sm" variant="ghost" aria-label={`Preview ${row.name}`} onClick={() => setPreview(row.id)}>
                            <Eye className="h-4 w-4" />
                          </Button>
                          <Button size="sm" variant="ghost" aria-label={`Send a test of ${row.name}`} disabled={!perms.canManage} onClick={() => setTest(row.id)}>
                            <Send className="h-4 w-4" />
                          </Button>
                          <Button size="sm" variant="ghost" aria-label={`Duplicate ${row.name}`} disabled={!perms.canManage || act.isPending} onClick={() => act.mutate(() => studioApi.duplicate(row.id))}>
                            <Copy className="h-4 w-4" />
                          </Button>
                          {row.status === "archived" ? (
                            <Button size="sm" variant="ghost" aria-label={`Restore ${row.name}`} disabled={!perms.canManage} onClick={() => act.mutate(async () => void (await studioApi.unarchive(row.id)))}>
                              <ArchiveRestore className="h-4 w-4" />
                            </Button>
                          ) : (
                            <Button
                              size="sm"
                              variant="ghost"
                              aria-label={`Archive ${row.name}`}
                              disabled={!perms.canManage}
                              onClick={() => {
                                if (window.confirm(`Archive "${row.name}"?`)) act.mutate(async () => void (await studioApi.archive(row.id)));
                              }}
                            >
                              <Archive className="h-4 w-4" />
                            </Button>
                          )}
                          <Button
                            size="sm"
                            variant="ghost"
                            aria-label={`Delete ${row.name}`}
                            title="Delete this template"
                            disabled={!perms.canManage || act.isPending}
                            onClick={() => {
                              if (window.confirm(`Delete "${row.name}" for good? All its versions are deleted too. Emails already sent are not affected.`)) {
                                act.mutate(async () => void (await studioApi.remove(row.id)));
                              }
                            }}
                          >
                            <Trash2 className="h-4 w-4 text-destructive" />
                          </Button>
                        </>
                      )}
                    </div>
                  </li>
                );
              })}
            </ul>
          </CardContent>
        </Card>
      ))}

      {legacyKey && <TemplateEditorDialog scope={{}} templateKey={legacyKey} onClose={() => { setLegacyKey(null); void refresh(); }} />}
      {preview && <TemplateDialog id={preview} mode="preview" onClose={() => setPreview(null)} />}
      {test && <TemplateDialog id={test} mode="test" onClose={() => setTest(null)} />}
    </div>
  );
}

/** Preview or test-send a stored template without opening the editor. */
function TemplateDialog({ id, mode, onClose }: { id: string; mode: "preview" | "test"; onClose: () => void }) {
  const perms = useStudioPermissions();
  const template = useQuery({ queryKey: studioKeys.template(id), queryFn: () => studioApi.get(id) });
  const [to, setTo] = useState(useAuthStore.getState().user?.email ?? "");
  const t = template.data;
  const key = t?.assignments[0]?.key ?? null;
  const send = useMutation({ mutationFn: async () => studioApi.test(t!.source_type, draftPayload(t!, {}), { type: "sample", key }, to.trim(), t!.id) });

  return (
    <Dialog open onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="max-h-[92vh] max-w-5xl overflow-y-auto">
        <DialogHeader>
          <DialogTitle>{mode === "preview" ? "Preview" : "Send a test email"}{t ? `: ${t.name}` : ""}</DialogTitle>
          <DialogDescription>{mode === "preview" ? "Drawn from the latest draft (or the published version when there is no draft). Nothing is sent." : "Sends the latest draft with sample values to one address. It starts nothing in ERPX."}</DialogDescription>
        </DialogHeader>
        {!t ? (
          <Skeleton className="h-40 w-full" />
        ) : mode === "preview" ? (
          <PreviewPane sourceType={t.source_type} getDraft={async () => draftPayload(t, {})} erpxKey={key} canUseStudents={perms.canUseStudents} refreshKey={0} />
        ) : (
          <div className="max-w-md space-y-3">
            <div className="space-y-1.5">
              <Label htmlFor="lib-test-to">Send to</Label>
              <Input id="lib-test-to" type="email" value={to} onChange={(e) => setTo(e.target.value)} />
            </div>
            {send.isError && <p role="alert" className="text-sm text-destructive">{errorMessage(send.error, "Could not send the test.")}</p>}
            {send.data && <p role="status" className={`text-sm ${send.data.sent ? "text-emerald-700 dark:text-emerald-400" : "text-destructive"}`}>{send.data.message}</p>}
            <Button disabled={!to.trim() || send.isPending} onClick={() => send.mutate()}>{send.isPending ? "Sending..." : "Send test"}</Button>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}
