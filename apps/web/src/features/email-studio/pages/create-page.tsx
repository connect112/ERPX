import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Braces, Code2, FileCode2, Layers3, Send, Upload } from "lucide-react";
import { useState } from "react";
import { useNavigate } from "react-router-dom";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { type DraftPayload, type ReactBuild, type SourceType, studioApi, studioKeys, useBrands, useCodeTemplates } from "@/features/email-studio/api/studio-api";
import { TestDialog } from "@/features/email-studio/components/test-dialog";
import { ReactWorkbench } from "@/features/email-studio/components/react-workbench";
import { useStudioPermissions } from "@/features/email-studio/lib/permissions";
import { EMPTY_DOC } from "@/features/email-studio/lib/studio";
import { errorMessage } from "@/features/institutions/lib/format";
import { selectClass } from "@/features/our-internships/components/letter-fields";

type Choice = "visual" | "html" | "code" | "react";
type ImportTab = "react" | "html";

/** Four ways to start an email: design it visually (the default), import HTML, import React Email code, or use an approved React Email template. */
export function CreatePage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const perms = useStudioPermissions();
  const brands = useBrands();
  const codeTemplates = useCodeTemplates();
  const categories = useQuery({ queryKey: ["email-studio", "categories"], queryFn: studioApi.categories, staleTime: Infinity });
  const [choice, setChoice] = useState<Choice>("visual");
  const [importTab, setImportTab] = useState<ImportTab>("react");
  const [name, setName] = useState("");
  const [category, setCategory] = useState("Custom Emails");
  const [brandId, setBrandId] = useState("");
  const [html, setHtml] = useState("");
  const [fileName, setFileName] = useState<string | null>(null);
  const [source, setSource] = useState("");
  const [subject, setSubject] = useState("");
  const [preheader, setPreheader] = useState("");
  const [testOpen, setTestOpen] = useState(false);

  const draftFor = (kind: SourceType, extra: Partial<DraftPayload> = {}): DraftPayload => ({
    name: name.trim() || "Untitled email",
    category,
    subject,
    preheader,
    brand_profile_id: brandId || null,
    signature_id: null,
    config: {},
    ...(kind === "react" ? { react_source: source } : {}),
    ...extra,
  });

  const create = useMutation({
    mutationFn: async (input: { source: SourceType; code?: string; publish?: boolean }) => {
      const code = codeTemplates.data?.find((c) => c.key === input.code);
      const created = await studioApi.create({
        name: name.trim() || code?.name || "Untitled email",
        source_type: input.source,
        category: code?.category && category === "Custom Emails" ? code.category : category,
        module: code?.module ?? null,
        subject: input.source === "react" ? subject : (code?.subject ?? ""),
        preheader: input.source === "react" ? preheader : "",
        brand_profile_id: brandId || null,
        signature_id: null,
        config: {},
        editor_json: input.source === "visual" ? EMPTY_DOC : undefined,
        html: input.source === "html" ? html : undefined,
        react_source: input.source === "react" ? source : undefined,
        code_template_key: input.code,
        code_props: input.code ? {} : undefined,
      });
      let notice: string | null = null;
      if (input.publish) {
        try {
          const published = await studioApi.publish(created.id);
          notice = `Published as version ${published.published_version_number}. It is not used for any ERPX email until you choose one under "Use for".`;
        } catch (error) {
          notice = `Saved as a draft, but it was not published: ${errorMessage(error, "it could not be published.")}`;
        }
      }
      return { created, notice };
    },
    onSuccess: ({ created, notice }) => {
      void queryClient.invalidateQueries({ queryKey: studioKeys.library });
      navigate(`/administration/email-templates/studio/${created.id}`, { state: notice ? { notice } : undefined });
    },
  });

  const options: { id: Choice; title: string; text: string; icon: typeof Layers3; badge?: string }[] = [
    { id: "visual", title: "Visual email builder", text: "Design with the React Email visual editor: text, images, buttons, columns and more, with no code.", icon: Layers3, badge: "Recommended" },
    { id: "html", title: "Import HTML", text: "Paste or upload an HTML email you already have. It is cleaned for safety and you can edit the source.", icon: FileCode2 },
    { id: "react", title: "Import React Email code", text: "Paste React Email code (from react.email or an AI assistant). It is read, never run, and turned into a safe, editable email.", icon: Braces },
    { id: "code", title: "Approved React Email templates", text: "Templates written and reviewed by developers. You edit their settings; they are never changed by uploading code.", icon: Code2 },
  ];

  const htmlCard = (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Your HTML</CardTitle>
        <CardDescription>Paste it, or upload an .html file. Scripts, forms, frames and risky styles are removed; your original is kept as written.</CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        <label className="inline-flex cursor-pointer items-center gap-2 rounded-md border px-3 py-2 text-sm hover:bg-muted">
          <Upload className="h-4 w-4" /> Upload an .html file
          <input
            type="file"
            accept=".html,.htm,text/html"
            className="sr-only"
            onChange={async (e) => {
              const file = e.target.files?.[0];
              e.target.value = "";
              if (!file) return;
              if (file.size > 600_000) return;
              setHtml(await file.text());
              setFileName(file.name);
              if (!name.trim()) setName(file.name.replace(/\.html?$/i, ""));
            }}
          />
        </label>
        {fileName && <span className="ml-2 text-sm text-muted-foreground">{fileName}</span>}
        <Textarea aria-label="HTML source" rows={12} className="font-mono text-xs" value={html} onChange={(e) => setHtml(e.target.value)} placeholder="<html>...</html>" />
        <Button disabled={!perms.canManage || !html.trim() || create.isPending} onClick={() => create.mutate({ source: "html" })}>
          {create.isPending ? "Importing..." : "Import and edit"}
        </Button>
      </CardContent>
    </Card>
  );

  const onBuilt = (built: ReactBuild) => {
    if (!built.ok) return;
    if (!subject.trim() && built.title) setSubject(built.title);
    if (!preheader.trim() && built.preheader) setPreheader(built.preheader);
    if (!name.trim() && built.title) setName(built.title);
  };

  return (
    <div className="space-y-6">
      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4" role="radiogroup" aria-label="How to create the email">
        {options.map((o) => (
          <button
            key={o.id}
            type="button"
            role="radio"
            aria-checked={choice === o.id}
            onClick={() => setChoice(o.id)}
            className={`rounded-lg border p-4 text-left transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring ${choice === o.id ? "border-primary bg-primary/5" : "hover:bg-muted"}`}
          >
            <o.icon className="mb-2 h-6 w-6 text-primary" aria-hidden="true" />
            <div className="flex flex-wrap items-center gap-2 font-medium">
              {o.title} {o.badge && <Badge variant="info">{o.badge}</Badge>}
            </div>
            <p className="mt-1 text-sm text-muted-foreground">{o.text}</p>
          </button>
        ))}
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Details</CardTitle>
          <CardDescription>You can change all of this later. Nothing is sent or published by creating an email.</CardDescription>
        </CardHeader>
        <CardContent className="grid gap-4 sm:grid-cols-3">
          <div className="space-y-1.5">
            <Label htmlFor="cr-name">Template name</Label>
            <Input id="cr-name" value={name} maxLength={200} placeholder="For example: Welcome to the programme" onChange={(e) => setName(e.target.value)} />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="cr-cat">Category</Label>
            <select id="cr-cat" className={selectClass} value={category} onChange={(e) => setCategory(e.target.value)}>
              {categories.data?.map((c) => (
                <option key={c} value={c}>{c}</option>
              ))}
            </select>
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="cr-brand">Brand profile</Label>
            <select id="cr-brand" className={selectClass} value={brandId} onChange={(e) => setBrandId(e.target.value)}>
              <option value="">Default brand</option>
              {brands.data?.map((b) => (
                <option key={b.id} value={b.id}>{b.name}</option>
              ))}
            </select>
          </div>
          {choice === "react" && importTab === "react" && (
            <>
              <div className="space-y-1.5 sm:col-span-2">
                <Label htmlFor="cr-subject">Subject</Label>
                <Input id="cr-subject" value={subject} maxLength={300} placeholder="One line. Placeholders such as {{student_name}} work here too." onChange={(e) => setSubject(e.target.value)} />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="cr-pre">Preview text</Label>
                <Input id="cr-pre" value={preheader} maxLength={200} placeholder="Filled from <Preview> in the code" onChange={(e) => setPreheader(e.target.value)} />
              </div>
            </>
          )}
        </CardContent>
      </Card>

      {choice === "visual" && (
        <Button disabled={!perms.canManage || create.isPending} onClick={() => create.mutate({ source: "visual" })}>
          {create.isPending ? "Creating..." : "Start designing"}
        </Button>
      )}

      {choice === "html" && htmlCard}

      {choice === "react" && (
        <div className="space-y-3">
          <div className="inline-flex rounded-md border p-0.5" role="tablist" aria-label="What to import">
            <Button role="tab" aria-selected={importTab === "react"} size="sm" variant={importTab === "react" ? "default" : "ghost"} onClick={() => setImportTab("react")}>
              React Email Code
            </Button>
            <Button role="tab" aria-selected={importTab === "html"} size="sm" variant={importTab === "html" ? "default" : "ghost"} onClick={() => setImportTab("html")}>
              HTML Code
            </Button>
          </div>

          {importTab === "html" && (
            <>
              <p className="text-sm text-muted-foreground">
                Use this tab when the React code cannot be imported: open the email on react.email (or run it in your own project), copy its HTML, and paste it here.
              </p>
              {htmlCard}
            </>
          )}

          {importTab === "react" && (
            <Card>
              <CardHeader>
                <CardTitle className="text-base">Your React Email code</CardTitle>
                <CardDescription>
                  Paste the code of a React Email template (TSX or JSX). The server reads it to build the email; it is never run. Supported: the React Email components
                  (Html, Head, Preview, Body, Container, Section, Row, Column, Heading, Text, Button, Link, Img, Hr, Tailwind), inline styles, fixed values, lists and ERPX
                  placeholders such as {"{{student_name}}"}.
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-3">
                <ReactWorkbench
                  source={source}
                  onSource={setSource}
                  preheader={preheader}
                  readOnly={!perms.canManage}
                  getDraft={async () => draftFor("react")}
                  erpxKey={null}
                  canUseStudents={perms.canUseStudents}
                  onBuilt={onBuilt}
                  onUseHtml={() => setImportTab("html")}
                />
                <div className="flex flex-wrap items-center gap-2 border-t pt-3">
                  <Button variant="outline" disabled={!perms.canManage || !source.trim() || create.isPending} onClick={() => create.mutate({ source: "react" })}>
                    {create.isPending ? "Saving..." : "Save draft"}
                  </Button>
                  <Button variant="outline" disabled={!perms.canManage || !source.trim()} onClick={() => setTestOpen(true)}>
                    <Send className="h-4 w-4" /> Send test
                  </Button>
                  <Button
                    disabled={!perms.canPublish || !source.trim() || !subject.trim() || create.isPending}
                    title={perms.canPublish ? (subject.trim() ? undefined : "Add a subject first") : "You need permission to publish email templates"}
                    onClick={() => {
                      if (window.confirm("Save and publish this email? It is not used for any ERPX email until you choose one under 'Use for'.")) create.mutate({ source: "react", publish: true });
                    }}
                  >
                    Save & publish
                  </Button>
                  <span className="text-xs text-muted-foreground">Saving keeps your code exactly as pasted. You can keep editing it afterwards.</span>
                </div>
              </CardContent>
            </Card>
          )}
        </div>
      )}

      {choice === "code" && (
        <div className="grid gap-3 md:grid-cols-2">
          {codeTemplates.data?.map((c) => (
            <Card key={c.key}>
              <CardHeader>
                <CardTitle className="text-base">{c.name}</CardTitle>
                <CardDescription>{c.description}</CardDescription>
              </CardHeader>
              <CardContent className="flex flex-wrap items-center justify-between gap-2">
                <div className="text-xs text-muted-foreground">
                  {c.category} · {c.props.length} settings
                </div>
                <Button size="sm" disabled={!perms.canManage || create.isPending} onClick={() => create.mutate({ source: "code", code: c.key })}>
                  Use this template
                </Button>
              </CardContent>
            </Card>
          ))}
          {codeTemplates.data?.length === 0 && <p className="text-sm text-muted-foreground">No approved templates are installed yet.</p>}
        </div>
      )}

      {create.isError && <p role="alert" className="text-sm text-destructive">{errorMessage(create.error, "Could not create the email.")}</p>}
      {!perms.canManage && perms.loaded && <p className="text-sm text-muted-foreground">You can look around, but creating emails needs permission to manage email templates.</p>}
      {testOpen && <TestDialog sourceType="react" getDraft={async () => draftFor("react")} erpxKey={null} onClose={() => setTestOpen(false)} />}
    </div>
  );
}
