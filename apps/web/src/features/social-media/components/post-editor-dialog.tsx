import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import type { Pillar, Post, PostFormat, PostPayload, Source, VerificationStatus } from "@/features/social-media/api/social-media-api";
import { FORMAT_LABEL, VERIFICATION_LABEL, toInputValue } from "@/features/social-media/lib/format";

const CAPTION_LIMIT = 2200;
const NATIVE_SELECT =
  "flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring disabled:opacity-50";

interface Props {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  post: Post | null;
  pillars: Pillar[];
  timeZone: string;
  canVerify: boolean;
  saving: boolean;
  error: string | null;
  onSave: (payload: PostPayload) => void;
}

function sourcesToText(post: Post | null): string {
  return (post?.sources ?? []).map((s) => [s.url, s.title, s.published_at].filter(Boolean).join(" | ")).join("\n");
}

function textToSources(text: string, existing: Source[]): Source[] {
  return text
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean)
    .map((line) => {
      const [url, title, published] = line.split("|").map((part) => part.trim());
      // Keep what was recorded when the source was first added (its retrieval date) so an unchanged source is unchanged.
      const before = existing.find((s) => s.url === url);
      return { url, title: title ?? "", published_at: published || null, retrieved_at: before?.retrieved_at ?? null };
    });
}

/** Writes a draft by hand. (AI drafting, research and artwork arrive in the next phase.) */
export function PostEditorDialog({ open, onOpenChange, post, pillars, timeZone, canVerify, saving, error, onSave }: Props) {
  const [title, setTitle] = useState("");
  const [format, setFormat] = useState<PostFormat>("image");
  const [pillar, setPillar] = useState("");
  const [objective, setObjective] = useState("");
  const [headline, setHeadline] = useState("");
  const [caption, setCaption] = useState("");
  const [cta, setCta] = useState("");
  const [hashtags, setHashtags] = useState("");
  const [altText, setAltText] = useState("");
  const [thumbnailText, setThumbnailText] = useState("");
  const [visualDirection, setVisualDirection] = useState("");
  const [slides, setSlides] = useState("");
  const [sources, setSources] = useState("");
  const [verification, setVerification] = useState<VerificationStatus>("not_required");
  const [highRisk, setHighRisk] = useState(false);
  const [timeSensitive, setTimeSensitive] = useState(false);
  const [scheduled, setScheduled] = useState("");

  useEffect(() => {
    if (!open) return;
    const c = post?.content;
    setTitle(post?.title ?? "");
    setFormat(post?.format ?? "image");
    setPillar(post?.pillar ?? "");
    setObjective(post?.objective ?? "");
    setHeadline(c?.headline ?? "");
    setCaption(c?.caption ?? "");
    setCta(c?.cta ?? "");
    setHashtags((c?.hashtags ?? []).map((h) => `#${h}`).join(" "));
    setAltText(c?.alt_text ?? "");
    setThumbnailText(c?.thumbnail_text ?? "");
    setVisualDirection(c?.visual_direction ?? "");
    setSlides((c?.slides ?? []).map((s) => [s.heading, s.body].filter(Boolean).join(" | ")).join("\n"));
    setSources(sourcesToText(post));
    setVerification(post?.verification_status ?? "not_required");
    setHighRisk(post?.high_risk ?? false);
    setTimeSensitive(post?.time_sensitive ?? false);
    setScheduled(toInputValue(post?.scheduled_at ?? null, timeZone));
  }, [open, post, timeZone]);

  const editingApproved = post?.status === "approved";

  function submit() {
    const slideRows = slides
      .split("\n")
      .map((line) => line.trim())
      .filter(Boolean)
      .map((line, index) => {
        const [heading, body] = line.split("|").map((part) => part.trim());
        const before = post?.content.slides[index];
        return { heading: heading ?? "", body: body ?? "", asset_key: before?.asset_key ?? null, alt_text: before?.alt_text ?? "" };
      });
    const payload: PostPayload = {
      title,
      format,
      pillar: pillar || null,
      objective: objective || null,
      content: {
        ...(post?.content ?? {}),
        headline,
        caption,
        cta,
        hashtags: hashtags.split(/[\s,]+/).filter(Boolean),
        alt_text: altText,
        thumbnail_text: thumbnailText,
        visual_direction: visualDirection,
        slides: slideRows,
      },
      sources: textToSources(sources, post?.sources ?? []),
      high_risk: highRisk,
      time_sensitive: timeSensitive,
    };
    if (canVerify || verification !== "verified") payload.verification_status = verification;
    if (scheduled) payload.scheduled_at = scheduled;
    else if (post?.scheduled_at) payload.clear_schedule = true;
    onSave(payload);
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[90vh] max-w-3xl overflow-y-auto">
        <DialogHeader>
          <DialogTitle>{post ? "Edit post" : "New draft"}</DialogTitle>
          <DialogDescription>
            Drafts are saved here and only go live after someone approves them. Nothing is published from this screen.
          </DialogDescription>
        </DialogHeader>

        {editingApproved && (
          <p className="rounded-md border border-amber-300 bg-amber-50 p-3 text-sm text-amber-900">
            This post is approved. Changing its content, format, sources or schedule withdraws the approval, and it will
            need to be reviewed again.
          </p>
        )}

        <div className="grid gap-4 sm:grid-cols-2">
          <div className="space-y-1.5 sm:col-span-2">
            <Label htmlFor="sm-title">Working title</Label>
            <Input id="sm-title" value={title} maxLength={200} onChange={(e) => setTitle(e.target.value)} />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="sm-format">Format</Label>
            <select id="sm-format" className={NATIVE_SELECT} value={format} onChange={(e) => setFormat(e.target.value as PostFormat)}>
              {(Object.keys(FORMAT_LABEL) as PostFormat[]).map((key) => (
                <option key={key} value={key}>
                  {FORMAT_LABEL[key]}
                </option>
              ))}
            </select>
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="sm-pillar">Content pillar</Label>
            <select id="sm-pillar" className={NATIVE_SELECT} value={pillar} onChange={(e) => setPillar(e.target.value)}>
              <option value="">None</option>
              {pillars.filter((p) => p.enabled || p.key === pillar).map((p) => (
                <option key={p.key} value={p.key}>
                  {p.label}
                </option>
              ))}
            </select>
          </div>
          <div className="space-y-1.5 sm:col-span-2">
            <Label htmlFor="sm-objective">Objective and audience</Label>
            <Input
              id="sm-objective"
              value={objective}
              maxLength={300}
              placeholder="e.g. Teach beginners what a SIEM does"
              onChange={(e) => setObjective(e.target.value)}
            />
          </div>
          <div className="space-y-1.5 sm:col-span-2">
            <Label htmlFor="sm-headline">Headline (short, one idea)</Label>
            <Input id="sm-headline" value={headline} maxLength={120} onChange={(e) => setHeadline(e.target.value)} />
          </div>
          <div className="space-y-1.5 sm:col-span-2">
            <div className="flex items-center justify-between">
              <Label htmlFor="sm-caption">Caption</Label>
              <span className={caption.length > CAPTION_LIMIT ? "text-xs text-destructive" : "text-xs text-muted-foreground"}>
                {caption.length}/{CAPTION_LIMIT}
              </span>
            </div>
            <Textarea id="sm-caption" rows={6} value={caption} maxLength={CAPTION_LIMIT} onChange={(e) => setCaption(e.target.value)} />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="sm-cta">Call to action</Label>
            <Input id="sm-cta" value={cta} maxLength={200} onChange={(e) => setCta(e.target.value)} />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="sm-hashtags">Hashtags (max 30)</Label>
            <Input id="sm-hashtags" value={hashtags} placeholder="#SIEM #SOC" onChange={(e) => setHashtags(e.target.value)} />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="sm-thumb">Text on the cover</Label>
            <Input id="sm-thumb" value={thumbnailText} maxLength={120} onChange={(e) => setThumbnailText(e.target.value)} />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="sm-alt">Alt text</Label>
            <Input id="sm-alt" value={altText} maxLength={420} onChange={(e) => setAltText(e.target.value)} />
          </div>
          <div className="space-y-1.5 sm:col-span-2">
            <Label htmlFor="sm-visual">Visual direction</Label>
            <Textarea id="sm-visual" rows={2} value={visualDirection} maxLength={1000} onChange={(e) => setVisualDirection(e.target.value)} />
          </div>
          {format === "carousel" && (
            <div className="space-y-1.5 sm:col-span-2">
              <Label htmlFor="sm-slides">Slides: one per line as “heading | body” (2 to 10)</Label>
              <Textarea id="sm-slides" rows={4} value={slides} onChange={(e) => setSlides(e.target.value)} />
            </div>
          )}
          <div className="space-y-1.5 sm:col-span-2">
            <Label htmlFor="sm-sources">Sources for factual claims: one per line as “link | title | published date”</Label>
            <Textarea id="sm-sources" rows={3} value={sources} onChange={(e) => setSources(e.target.value)} />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="sm-verification">Fact check</Label>
            <select
              id="sm-verification"
              className={NATIVE_SELECT}
              value={verification}
              onChange={(e) => setVerification(e.target.value as VerificationStatus)}
            >
              {(Object.keys(VERIFICATION_LABEL) as VerificationStatus[]).map((key) => (
                <option key={key} value={key} disabled={key === "verified" && !canVerify && verification !== "verified"}>
                  {VERIFICATION_LABEL[key]}
                </option>
              ))}
            </select>
            {!canVerify && <p className="text-xs text-muted-foreground">Only someone who can approve posts can mark claims as verified.</p>}
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="sm-when">Planned time ({timeZone})</Label>
            <Input id="sm-when" type="datetime-local" value={scheduled} onChange={(e) => setScheduled(e.target.value)} />
            <p className="text-xs text-muted-foreground">A plan only. Automatic scheduling arrives with the publishing phase.</p>
          </div>
          <label className="flex items-center gap-2 text-sm">
            <input type="checkbox" checked={timeSensitive} onChange={(e) => setTimeSensitive(e.target.checked)} />
            Time-sensitive (news, a new vulnerability)
          </label>
          <label className="flex items-center gap-2 text-sm">
            <input type="checkbox" checked={highRisk} onChange={(e) => setHighRisk(e.target.checked)} />
            High-risk security claim (needs extra review)
          </label>
        </div>

        {error && <p className="text-sm text-destructive">{error}</p>}
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button onClick={submit} disabled={saving || !title.trim()}>
            {saving ? "Saving..." : post ? "Save changes" : "Save draft"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
