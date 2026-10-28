import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Code2, FileCode2, Layers3, Upload } from "lucide-react";
import { useState } from "react";
import { useNavigate } from "react-router-dom";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { type SourceType, studioApi, studioKeys, useBrands, useCodeTemplates } from "@/features/email-studio/api/studio-api";
import { useStudioPermissions } from "@/features/email-studio/lib/permissions";
import { EMPTY_DOC } from "@/features/email-studio/lib/studio";
import { errorMessage } from "@/features/institutions/lib/format";
import { selectClass } from "@/features/our-internships/components/letter-fields";
import { useQuery } from "@tanstack/react-query";

type Choice = "visual" | "html" | "code";

/** Three ways to start an email: design it visually (the default), import HTML, or use an approved React Email template. */
export function CreatePage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const perms = useStudioPermissions();
  const brands = useBrands();
  const codeTemplates = useCodeTemplates();
  const categories = useQuery({ queryKey: ["email-studio", "categories"], queryFn: studioApi.categories, staleTime: Infinity });
  const [choice, setChoice] = useState<Choice>("visual");
  const [name, setName] = useState("");
  const [category, setCategory] = useState("Custom Emails");
  const [brandId, setBrandId] = useState("");
  const [html, setHtml] = useState("");
  const [fileName, setFileName] = useState<string | null>(null);

  const create = useMutation({
    mutationFn: (input: { source: SourceType; code?: string }) => {
      const code = codeTemplates.data?.find((c) => c.key === input.code);
      return studioApi.create({
        name: name.trim() || code?.name || "Untitled email",
        source_type: input.source,
        category: code?.category && category === "Custom Emails" ? code.category : category,
        module: code?.module ?? null,
        subject: code?.subject ?? "",
        preheader: "",
        brand_profile_id: brandId || null,
        signature_id: null,
        config: {},
        editor_json: input.source === "visual" ? EMPTY_DOC : undefined,
        html: input.source === "html" ? html : undefined,
        code_template_key: input.code,
        code_props: input.code ? {} : undefined,
      });
    },
    onSuccess: (t) => {
      void queryClient.invalidateQueries({ queryKey: studioKeys.library });
      navigate(`/administration/email-templates/studio/${t.id}`);
    },
  });

  const options: { id: Choice; title: string; text: string; icon: typeof Layers3; badge?: string }[] = [
    { id: "visual", title: "Visual email builder", text: "Design with the React Email visual editor: text, images, buttons, columns and more, with no code.", icon: Layers3, badge: "Recommended" },
    { id: "html", title: "Import HTML", text: "Paste or upload an HTML email you already have. It is cleaned for safety and you can edit the source.", icon: FileCode2 },
    { id: "code", title: "Approved React Email templates", text: "Templates written and reviewed by developers. You edit their settings; they are never changed by uploading code.", icon: Code2 },
  ];

  return (
    <div className="space-y-6">
      <div className="grid gap-3 md:grid-cols-3" role="radiogroup" aria-label="How to create the email">
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
            <div className="flex items-center gap-2 font-medium">
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
        </CardContent>
      </Card>

      {choice === "visual" && (
        <Button disabled={!perms.canManage || create.isPending} onClick={() => create.mutate({ source: "visual" })}>
          {create.isPending ? "Creating..." : "Start designing"}
        </Button>
      )}

      {choice === "html" && (
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
    </div>
  );
}
