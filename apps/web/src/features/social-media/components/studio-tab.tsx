import { Sparkles } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { useMyRoles } from "@/features/auth/api/authorization-hooks";
import type { Post, PostFormat } from "@/features/social-media/api/social-media-api";
import { useGenerate, useHistory, useResearch, useSocialSettings, useUsage } from "@/features/social-media/api/social-media-hooks";
import { FORMAT_LABEL, errorMessage } from "@/features/social-media/lib/format";

const NATIVE_SELECT =
  "flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring disabled:opacity-50";

interface Props {
  selected: string[];
  onSelectedChange: (ids: string[]) => void;
  onOpenPosts: () => void;
}

/** Drafts a post with AI. The result is always a draft: it is checked automatically and waits for a person's review. */
export function StudioTab({ selected, onSelectedChange, onOpenPosts }: Props) {
  const settings = useSocialSettings();
  const research = useResearch({ limit: 20 });
  const history = useHistory();
  const usage = useUsage();
  const generate = useGenerate();
  const me = useMyRoles();
  const canManage = (me.data?.is_superuser ?? false) || (me.data?.effective_permissions ?? []).includes("social_media.manage");

  const [topic, setTopic] = useState("");
  const [format, setFormat] = useState<PostFormat>("image");
  const [pillar, setPillar] = useState("");
  const [persona, setPersona] = useState("");
  const [notes, setNotes] = useState("");
  const [timeSensitive, setTimeSensitive] = useState(false);
  const [made, setMade] = useState<Post | null>(null);
  const [error, setError] = useState<string | null>(null);

  const items = research.data?.items ?? [];
  const pickedItems = items.filter((i) => selected.includes(i.id));

  function toggle(id: string) {
    if (selected.includes(id)) onSelectedChange(selected.filter((s) => s !== id));
    else if (selected.length < 5) onSelectedChange([...selected, id]);
  }

  function submit() {
    setError(null);
    setMade(null);
    generate.mutate(
      {
        topic: topic.trim(),
        format,
        pillar: pillar || null,
        persona_key: persona || null,
        research_item_ids: selected,
        notes: notes.trim(),
        time_sensitive: timeSensitive,
      },
      {
        onSuccess: (post) => {
          setMade(post);
          onSelectedChange([]);
        },
        onError: (e) => setError(errorMessage(e, "Couldn't draft the post.")),
      },
    );
  }

  if (!canManage) return <p className="text-sm text-muted-foreground">Drafting with AI needs the social_media.manage permission.</p>;

  return (
    <div className="space-y-6">
      {usage.data && !usage.data.ai_configured && (
        <p className="rounded-md border border-amber-300 bg-amber-50 p-3 text-sm text-amber-900">
          AI drafting isn&apos;t configured on this server (no AI key is set), so it can&apos;t write drafts here.
        </p>
      )}
      {history.data && history.data.suggestions.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>What to cover next</CardTitle>
            <CardDescription>From the mix of your recent posts against your targets.</CardDescription>
          </CardHeader>
          <CardContent>
            <ul className="list-disc space-y-1 pl-5 text-sm">
              {history.data.suggestions.map((s) => (
                <li key={s}>{s}</li>
              ))}
            </ul>
          </CardContent>
        </Card>
      )}

      <Card>
        <CardHeader>
          <CardTitle>New draft with AI</CardTitle>
          <CardDescription>
            The AI uses only facts from the research you select. With no research, it writes evergreen teaching content and makes no claims about recent events.
          </CardDescription>
        </CardHeader>
        <CardContent className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <div className="space-y-1.5 sm:col-span-2">
            <Label htmlFor="st-topic">Topic</Label>
            <Input id="st-topic" value={topic} maxLength={300} placeholder="e.g. What a SOC analyst does in a day" onChange={(e) => setTopic(e.target.value)} />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="st-format">Format</Label>
            <select id="st-format" className={NATIVE_SELECT} value={format} onChange={(e) => setFormat(e.target.value as PostFormat)}>
              {(Object.keys(FORMAT_LABEL) as PostFormat[]).map((key) => (
                <option key={key} value={key}>
                  {FORMAT_LABEL[key]}
                </option>
              ))}
            </select>
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="st-pillar">Content pillar</Label>
            <select id="st-pillar" className={NATIVE_SELECT} value={pillar} onChange={(e) => setPillar(e.target.value)}>
              <option value="">None</option>
              {(settings.data?.pillars ?? []).filter((p) => p.enabled).map((p) => (
                <option key={p.key} value={p.key}>
                  {p.label}
                </option>
              ))}
            </select>
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="st-persona">Audience</Label>
            <select id="st-persona" className={NATIVE_SELECT} value={persona} onChange={(e) => setPersona(e.target.value)}>
              <option value="">General</option>
              {(settings.data?.personas ?? []).map((p) => (
                <option key={p.key} value={p.key}>
                  {p.label}
                </option>
              ))}
            </select>
          </div>
          <label className="flex items-center gap-2 self-end text-sm">
            <input type="checkbox" checked={timeSensitive} onChange={(e) => setTimeSensitive(e.target.checked)} />
            Time-sensitive
          </label>
          <div className="space-y-1.5 sm:col-span-2">
            <Label htmlFor="st-notes">Notes for the writer (optional)</Label>
            <Textarea id="st-notes" rows={2} maxLength={500} value={notes} onChange={(e) => setNotes(e.target.value)} />
          </div>

          <div className="space-y-2 sm:col-span-2">
            <span className="text-sm font-medium">Research to base it on (up to 5)</span>
            {pickedItems.length === 0 && <p className="text-xs text-muted-foreground">None selected. Pick items below, or use &quot;Draft a post from this&quot; on the Research tab.</p>}
            <div className="max-h-56 space-y-1 overflow-y-auto rounded-md border p-2">
              {items.length === 0 && <p className="p-2 text-xs text-muted-foreground">No research yet. Read the sources on the Research tab first.</p>}
              {items.map((item) => (
                <div key={item.id} className="flex items-start gap-2 rounded p-1.5 text-sm hover:bg-accent">
                  <input
                    id={`research-${item.id}`}
                    type="checkbox"
                    className="mt-1"
                    aria-label={item.title}
                    checked={selected.includes(item.id)}
                    onChange={() => toggle(item.id)}
                  />
                  <label htmlFor={`research-${item.id}`} className="min-w-0 flex-1 cursor-pointer">
                    <span className="block truncate">{item.title}</span>
                    <span className="text-xs text-muted-foreground">
                      {item.source === "cisa_kev" ? "Known exploited" : "Advisory"}
                      {item.published_at ? ` · ${item.published_at.slice(0, 10)}` : ""}
                    </span>
                  </label>
                </div>
              ))}
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-3 sm:col-span-2">
            <Button onClick={submit} disabled={generate.isPending || topic.trim().length < 3}>
              <Sparkles className="mr-1 h-4 w-4" />
              {generate.isPending ? "Drafting... (up to a minute)" : "Draft with AI"}
            </Button>
            {usage.data && (
              <span className="text-xs text-muted-foreground">
                This month: about ₹{usage.data.spent_inr.toFixed(2)} of AI cost (estimate){usage.data.budget_inr > 0 ? ` of ₹${usage.data.budget_inr} budget` : ", no budget limit"}.
              </span>
            )}
          </div>
          {error && (
            <p role="alert" className="text-sm text-destructive sm:col-span-2">
              {error}
            </p>
          )}
        </CardContent>
      </Card>

      {made && (
        <Card>
          <CardHeader>
            <CardTitle>Draft saved: {made.title}</CardTitle>
            <CardDescription>It is a draft. Nothing is approved or published.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3 text-sm">
            <p className="whitespace-pre-wrap">{made.content.caption}</p>
            {made.warnings.length > 0 ? (
              <ul className="space-y-1 text-xs">
                {made.warnings.map((w, i) => (
                  <li key={i} className={w.severity === "blocking" ? "text-destructive" : "text-amber-700"}>
                    {w.severity === "blocking" ? "Blocking: " : "Check: "}
                    {w.message}
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-xs text-muted-foreground">The automatic checks found nothing to flag. A person still reviews it before approval.</p>
            )}
            <Button onClick={onOpenPosts}>Open in Posts</Button>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
