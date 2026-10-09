import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { Textarea } from "@/components/ui/textarea";
import type { Experiment, ExperimentMetric, ExperimentVariable, ExperimentVariant } from "@/features/social-media/api/social-media-api";
import { useAnalyticsPosts, useCreateExperiment, useDeleteExperiment, useExperiment, useExperiments, useUpdateExperiment } from "@/features/social-media/api/social-media-hooks";
import { errorMessage, formatInZone } from "@/features/social-media/lib/format";
import { NOT_AVAILABLE, formatNumber, formatRate } from "@/features/social-media/lib/numbers";

const NATIVE_SELECT = "flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring disabled:opacity-50";

const VARIABLES: Record<ExperimentVariable, string> = {
  hook: "Hook style",
  cover_style: "Cover style",
  format: "Format",
  time: "Posting time",
  cta: "Call to action",
  other: "Something else",
};
const METRICS: Record<ExperimentMetric, string> = {
  reach: "Accounts reached",
  views: "Views",
  saved: "Saves",
  shares: "Shares",
  likes: "Likes",
  comments: "Comments",
  total_interactions: "Interactions (Instagram's figure)",
  interactions: "Interactions (likes + comments + saves + shares)",
  er_reach: "Engagement rate by reach",
};
const STATUS_VARIANT = { planned: "secondary", running: "info", concluded: "success", dropped: "outline" } as const;
const MIN_VARIANTS = 2;
const MAX_VARIANTS = 4;

function PostPicker({ chosen, taken, onChange }: { chosen: string[]; taken: Set<string>; onChange: (ids: string[]) => void }) {
  const posts = useAnalyticsPosts();
  const options = (posts.data?.items ?? []).filter((p) => p.post_id);
  if (posts.isLoading) return <Skeleton className="h-8 w-full" />;
  if (options.length === 0) return <p className="text-xs text-muted-foreground">No ERPX posts are on Instagram yet. Posts made in the Studio and published will appear here.</p>;
  return (
    <ul className="max-h-32 space-y-1 overflow-y-auto rounded-md border p-2 text-sm">
      {options.map((p) => {
        const id = p.post_id as string;
        const elsewhere = taken.has(id) && !chosen.includes(id);
        return (
          <li key={id}>
            <label className={`flex items-start gap-2 ${elsewhere ? "opacity-50" : ""}`}>
              <input type="checkbox" className="mt-1" disabled={elsewhere} checked={chosen.includes(id)} onChange={(e) => onChange(e.target.checked ? [...chosen, id] : chosen.filter((x) => x !== id))} />
              <span className="min-w-0 break-words">
                {p.title ?? p.caption} <span className="text-xs text-muted-foreground">({p.kind}, {p.posted_at ? formatInZone(p.posted_at, "Asia/Kolkata") : "date unknown"})</span>
              </span>
            </label>
          </li>
        );
      })}
    </ul>
  );
}

function VariantsEditor({ variants, onChange }: { variants: ExperimentVariant[]; onChange: (v: ExperimentVariant[]) => void }) {
  const taken = new Set(variants.flatMap((v) => v.post_ids));
  return (
    <div className="space-y-3">
      {variants.map((v, i) => (
        <div key={i} className="space-y-2 rounded-md border p-3">
          <div className="flex items-center gap-2">
            <Input aria-label={`Variant ${i + 1} name`} placeholder={`Variant ${i + 1} (for example "Question hook")`} maxLength={60} value={v.label} onChange={(e) => onChange(variants.map((x, j) => (j === i ? { ...x, label: e.target.value } : x)))} />
            {variants.length > MIN_VARIANTS && (
              <Button type="button" size="sm" variant="ghost" onClick={() => onChange(variants.filter((_, j) => j !== i))}>
                Remove
              </Button>
            )}
          </div>
          <PostPicker chosen={v.post_ids} taken={taken} onChange={(ids) => onChange(variants.map((x, j) => (j === i ? { ...x, post_ids: ids } : x)))} />
        </div>
      ))}
      {variants.length < MAX_VARIANTS && (
        <Button type="button" size="sm" variant="outline" onClick={() => onChange([...variants, { label: "", post_ids: [] }])}>
          Add a variant
        </Button>
      )}
    </div>
  );
}

function CreateDialog({ onClose }: { onClose: () => void }) {
  const create = useCreateExperiment();
  const [name, setName] = useState("");
  const [hypothesis, setHypothesis] = useState("");
  const [variable, setVariable] = useState<ExperimentVariable>("hook");
  const [metric, setMetric] = useState<ExperimentMetric>("reach");
  const [audience, setAudience] = useState("");
  const [variants, setVariants] = useState<ExperimentVariant[]>([
    { label: "", post_ids: [] },
    { label: "", post_ids: [] },
  ]);
  const [error, setError] = useState<string | null>(null);
  const ready = name.trim() && hypothesis.trim() && variants.every((v) => v.label.trim());

  function submit() {
    setError(null);
    create.mutate({ name, hypothesis, variable, metric, audience: audience.trim() || undefined, variants }, { onSuccess: onClose, onError: (e) => setError(errorMessage(e, "Couldn't save the experiment.")) });
  }

  return (
    <Dialog open onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-xl">
        <DialogHeader>
          <DialogTitle>New experiment</DialogTitle>
          <DialogDescription>Change one thing, pick the figure to watch, and record which posts belong to which variant. ERPX shows what was observed; it never declares a cause.</DialogDescription>
        </DialogHeader>
        <div className="space-y-3 text-sm">
          <div className="space-y-1">
            <Label htmlFor="exp-name">Name</Label>
            <Input id="exp-name" maxLength={160} value={name} onChange={(e) => setName(e.target.value)} placeholder="Question vs statement hooks" />
          </div>
          <div className="space-y-1">
            <Label htmlFor="exp-hyp">What do you expect, and why?</Label>
            <Textarea id="exp-hyp" rows={2} maxLength={600} value={hypothesis} onChange={(e) => setHypothesis(e.target.value)} />
          </div>
          <div className="grid gap-3 sm:grid-cols-2">
            <div className="space-y-1">
              <Label htmlFor="exp-var">What changes between variants</Label>
              <select id="exp-var" className={NATIVE_SELECT} value={variable} onChange={(e) => setVariable(e.target.value as ExperimentVariable)}>
                {Object.entries(VARIABLES).map(([k, v]) => (
                  <option key={k} value={k}>
                    {v}
                  </option>
                ))}
              </select>
            </div>
            <div className="space-y-1">
              <Label htmlFor="exp-metric">Figure to compare</Label>
              <select id="exp-metric" className={NATIVE_SELECT} value={metric} onChange={(e) => setMetric(e.target.value as ExperimentMetric)}>
                {Object.entries(METRICS).map(([k, v]) => (
                  <option key={k} value={k}>
                    {v}
                  </option>
                ))}
              </select>
            </div>
          </div>
          <div className="space-y-1">
            <Label htmlFor="exp-aud">Audience (optional)</Label>
            <Input id="exp-aud" maxLength={300} value={audience} onChange={(e) => setAudience(e.target.value)} placeholder="Everyone who follows the profile" />
          </div>
          <div className="space-y-1">
            <p className="text-sm font-medium leading-none">Variants and their posts</p>
            <p className="text-xs text-muted-foreground">Posts can be added later too. Each post belongs to one variant only.</p>
            <VariantsEditor variants={variants} onChange={setVariants} />
          </div>
          {error && (
            <p role="alert" className="text-destructive">
              {error}
            </p>
          )}
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={onClose} disabled={create.isPending}>
            Cancel
          </Button>
          <Button onClick={submit} disabled={!ready || create.isPending}>
            {create.isPending ? "Saving…" : "Save experiment"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function fmtValue(metric: string, value: number | null): string {
  return metric === "er_reach" ? formatRate(value) : formatNumber(value);
}

function DetailDialog({ id, canManage, onClose }: { id: string; canManage: boolean; onClose: () => void }) {
  const detail = useExperiment(id);
  const update = useUpdateExperiment();
  const remove = useDeleteExperiment();
  const [conclusion, setConclusion] = useState<string | null>(null);
  const [variants, setVariants] = useState<ExperimentVariant[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const exp = detail.data?.experiment;
  const results = detail.data?.results;
  const finished = exp?.status === "concluded" || exp?.status === "dropped";

  function save(payload: Parameters<typeof update.mutate>[0]["payload"], done?: () => void) {
    setError(null);
    update.mutate({ id, payload }, { onSuccess: () => done?.(), onError: (e) => setError(errorMessage(e, "That didn't work.")) });
  }

  return (
    <Dialog open onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-2xl">
        <DialogHeader>
          <DialogTitle>{exp?.name ?? "Experiment"}</DialogTitle>
          <DialogDescription>{exp?.hypothesis}</DialogDescription>
        </DialogHeader>
        {detail.isLoading ? (
          <Skeleton className="h-32 w-full" />
        ) : !exp || !results ? (
          <p className="text-sm text-destructive">Couldn&apos;t load this experiment.</p>
        ) : (
          <div className="space-y-3 text-sm">
            <p className="text-xs text-muted-foreground">
              Changing: {VARIABLES[exp.variable]} · Comparing: {METRICS[exp.metric]}
              {exp.audience ? ` · Audience: ${exp.audience}` : ""}
              {exp.started_on ? ` · Started ${exp.started_on}` : ""}
              {exp.ended_on ? ` · Ended ${exp.ended_on}` : ""}
            </p>
            <div className="rounded-md border p-3">
              <p className="font-medium">What was observed</p>
              <p>{results.reading}</p>
              <p className="mt-1 text-xs text-muted-foreground">{results.caution}</p>
            </div>
            {results.variants.map((v) => (
              <div key={v.label} className="rounded-md border p-3">
                <p className="font-medium">
                  {v.label}{" "}
                  <span className="text-xs font-normal text-muted-foreground">
                    {v.n} post(s) with a figure · median {fmtValue(results.metric, v.median)}
                    {v.low !== null && v.high !== null ? ` · range ${fmtValue(results.metric, v.low)} to ${fmtValue(results.metric, v.high)}` : ""}
                  </span>
                </p>
                {v.posts.length === 0 ? (
                  <p className="text-xs text-muted-foreground">No posts added yet.</p>
                ) : (
                  <ul className="mt-1 space-y-0.5 text-xs">
                    {v.posts.map((p) => (
                      <li key={p.post_id}>
                        {p.title ?? "Post"}: {p.value !== null ? fmtValue(results.metric, p.value) : !p.published ? "not on Instagram yet" : !p.insights_read ? "figures not read yet" : NOT_AVAILABLE}
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            ))}
            {canManage && !finished && (
              <div className="space-y-2">
                <p className="text-sm font-medium leading-none">Posts in each variant</p>
                <VariantsEditor variants={variants ?? exp.variants} onChange={setVariants} />
                {variants && (
                  <Button size="sm" variant="outline" disabled={update.isPending || variants.some((v) => !v.label.trim())} onClick={() => save({ variants }, () => setVariants(null))}>
                    Save posts
                  </Button>
                )}
              </div>
            )}
            {canManage && (
              <div className="space-y-1">
                <Label htmlFor="exp-concl">What you concluded (and how unsure you are)</Label>
                <Textarea id="exp-concl" rows={3} maxLength={2000} value={conclusion ?? exp.conclusion ?? ""} onChange={(e) => setConclusion(e.target.value)} />
                {conclusion !== null && conclusion !== (exp.conclusion ?? "") && (
                  <Button size="sm" variant="outline" disabled={update.isPending} onClick={() => save({ conclusion }, () => setConclusion(null))}>
                    Save conclusion
                  </Button>
                )}
              </div>
            )}
            {error && (
              <p role="alert" className="text-destructive">
                {error}
              </p>
            )}
          </div>
        )}
        <DialogFooter className="gap-2 sm:gap-0">
          {canManage && exp && exp.status === "planned" && (
            <Button variant="outline" disabled={update.isPending} onClick={() => save({ status: "running" })}>
              Start
            </Button>
          )}
          {canManage && exp && exp.status === "running" && (
            <Button variant="outline" disabled={update.isPending} onClick={() => save({ status: "concluded" })}>
              Mark finished
            </Button>
          )}
          {canManage && exp && !finished && (
            <Button variant="outline" disabled={update.isPending} onClick={() => save({ status: "dropped" })}>
              Drop
            </Button>
          )}
          {canManage && exp && (
            <Button variant="outline" disabled={remove.isPending} onClick={() => remove.mutate(id, { onSuccess: onClose, onError: (e) => setError(errorMessage(e, "Couldn't delete.")) })}>
              Delete
            </Button>
          )}
          <Button onClick={onClose}>Close</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

/** Planned comparisons and what was observed. Never a "winner" and never a cause. */
export function ExperimentsPanel({ canManage }: { canManage: boolean }) {
  const list = useExperiments();
  const [creating, setCreating] = useState(false);
  const [openId, setOpenId] = useState<string | null>(null);
  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <h2 className="text-lg font-semibold">Experiments</h2>
          <p className="text-sm text-muted-foreground">Try one change at a time (a hook style, a cover style, a posting time) and record what you saw. A few posts can&apos;t prove anything, and ERPX says so.</p>
        </div>
        {canManage && <Button size="sm" onClick={() => setCreating(true)}>New experiment</Button>}
      </div>
      {list.isLoading ? (
        <Skeleton className="h-16 w-full" />
      ) : (list.data ?? []).length === 0 ? (
        <Card>
          <CardContent className="py-8 text-center text-sm text-muted-foreground">No experiments yet.</CardContent>
        </Card>
      ) : (
        (list.data as Experiment[]).map((e) => (
          <Card key={e.id}>
            <CardContent className="flex flex-wrap items-center justify-between gap-2 p-4">
              <div className="min-w-0">
                <p className="font-medium">{e.name}</p>
                <p className="text-xs text-muted-foreground">
                  {VARIABLES[e.variable]} · {METRICS[e.metric]} · {e.variants.map((v) => `${v.label} (${v.post_ids.length})`).join(" vs ")}
                </p>
              </div>
              <div className="flex items-center gap-2">
                <Badge variant={STATUS_VARIANT[e.status]}>{e.status}</Badge>
                <Button size="sm" variant="outline" onClick={() => setOpenId(e.id)}>
                  Open
                </Button>
              </div>
            </CardContent>
          </Card>
        ))
      )}
      {creating && <CreateDialog onClose={() => setCreating(false)} />}
      {openId && <DetailDialog id={openId} canManage={canManage} onClose={() => setOpenId(null)} />}
    </div>
  );
}
