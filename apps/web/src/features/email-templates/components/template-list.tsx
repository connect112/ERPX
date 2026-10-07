import { Mail, Paperclip, Pencil } from "lucide-react";
import { useMemo, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import type { TemplateScope, TemplateSummary } from "@/features/email-templates/api/email-templates-api";
import { useEmailTemplates } from "@/features/email-templates/api/email-templates-hooks";
import { TemplateEditorDialog } from "@/features/email-templates/components/template-editor";

/** The emails that can be edited, grouped by what they are for. Pick one to open its editor. */
export function TemplateList({ scope }: { scope: TemplateScope }) {
  const { data, isLoading, isError } = useEmailTemplates(scope);
  const [openKey, setOpenKey] = useState<string | null>(null);

  const groups = useMemo(() => {
    const byCategory = new Map<string, TemplateSummary[]>();
    for (const template of data ?? []) byCategory.set(template.category, [...(byCategory.get(template.category) ?? []), template]);
    return [...byCategory.entries()];
  }, [data]);

  if (isLoading) return <Skeleton className="h-48 w-full" />;
  if (isError) return <p className="text-sm text-destructive">Could not load the email templates.</p>;

  return (
    <div className="space-y-6">
      {groups.map(([category, templates]) => (
        <Card key={category}>
          <CardHeader>
            <CardTitle className="text-base">{category}</CardTitle>
            <CardDescription>
              {templates.length} email{templates.length === 1 ? "" : "s"}
            </CardDescription>
          </CardHeader>
          <CardContent className="p-0">
            <ul className="divide-y">
              {templates.map((template) => (
                <li key={template.key} className="flex flex-wrap items-center justify-between gap-3 px-6 py-4">
                  <div className="min-w-0 flex-1">
                    <p className="flex items-center gap-2 font-medium">
                      <Mail className="h-4 w-4 text-muted-foreground" />
                      {template.name}
                      {template.has_attachment && (
                        <span title="A PDF is attached automatically">
                          <Paperclip className="h-3.5 w-3.5 text-muted-foreground" aria-label="Has an attachment" />
                        </span>
                      )}
                    </p>
                    <p className="text-sm text-muted-foreground">{template.description}</p>
                    <p className="text-xs text-muted-foreground">Sent: {template.when_sent}</p>
                  </div>
                  <div className="flex items-center gap-3">
                    <div className="text-right text-xs">
                      <Badge variant={template.customised ? "info" : "secondary"}>
                        {template.customised
                          ? "Edited"
                          : template.inherited
                            ? "Organisation's wording"
                            : "Default"}
                      </Badge>
                      {template.updated_at && template.customised && (
                        <p className="mt-0.5 text-muted-foreground">
                          {new Date(template.updated_at).toLocaleDateString()}
                          {template.updated_by_name ? ` · ${template.updated_by_name}` : ""}
                        </p>
                      )}
                    </div>
                    <Button size="sm" variant="outline" onClick={() => setOpenKey(template.key)}>
                      <Pencil className="h-4 w-4" />
                      View / edit
                    </Button>
                  </div>
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>
      ))}
      {openKey && <TemplateEditorDialog scope={scope} templateKey={openKey} onClose={() => setOpenKey(null)} />}
    </div>
  );
}
