import { useEffect, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import type { Design, Post, Template } from "@/features/social-media/api/social-media-api";
import {
  useAssets,
  useNewBackground,
  useProofread,
  useRemoveArtwork,
  useSaveAndDraw,
  useUsage,
} from "@/features/social-media/api/social-media-hooks";
import { GridPreview } from "@/features/social-media/components/grid-preview";
import { errorMessage } from "@/features/social-media/lib/format";

const NATIVE_SELECT =
  "flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring disabled:opacity-50";

const TEMPLATES: { value: Template; label: string; hint: string }[] = [
  { value: "editorial", label: "Editorial (light)", hint: "Plain light background, one headline. The default." },
  { value: "statement", label: "Statement (dark)", hint: "Dark background, one bold line." },
  { value: "photo", label: "Photo", hint: "A photograph or background behind the headline, darkened so it stays readable." },
  { value: "screenshot", label: "Screenshot", hint: "A real screenshot framed above a caption." },
];

interface Props {
  post: Post | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

/**
 * Chooses how a post's cover looks and draws it. Every word and the logo are drawn by code, so the picture always
 * says exactly what the post says. Changing only the wording redraws from the stored picture; a new AI background
 * replaces only the picture.
 */
export function ArtworkDialog({ post, open, onOpenChange }: Props) {
  const assets = useAssets();
  const usage = useUsage();
  const draw = useSaveAndDraw();
  const remove = useRemoveArtwork();
  const background = useNewBackground();
  const proofread = useProofread();

  const [template, setTemplate] = useState<Template>("editorial");
  const [pictureId, setPictureId] = useState<string | null>(null);
  const [kicker, setKicker] = useState("");
  const [headline, setHeadline] = useState("");
  const [subline, setSubline] = useState("");
  const [credit, setCredit] = useState("");
  const [showLogo, setShowLogo] = useState(true);
  const [direction, setDirection] = useState("");
  const [showGrid, setShowGrid] = useState(false);
  const [message, setMessage] = useState<{ ok: boolean; text: string } | null>(null);
  const [proof, setProof] = useState<{ ok: boolean; issues: { text: string; suggestion: string }[] } | null>(null);

  const postId = post?.id;
  useEffect(() => {
    if (!open || !post) return;
    const d = post.design ?? {};
    setTemplate(d.template ?? "editorial");
    setPictureId(d.background_asset_id ?? null);
    setKicker(d.kicker ?? "");
    setHeadline(d.headline ?? "");
    setSubline(d.subline ?? "");
    setCredit(d.credit ?? "");
    setShowLogo(d.show_logo ?? true);
    setDirection("");
    setShowGrid(false);
    setMessage(null);
    setProof(null);
    // Only when the dialog opens for a post, not each time the post is refreshed after a change.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, postId]);

  if (!post) return null;
  const files = post.artwork?.files ?? [];
  const stale = post.warnings.some((w) => w.code === "chk_artwork_stale");
  const pictures = (assets.data ?? []).filter((a) => a.kind !== "logo");
  const needsPicture = template === "photo" || template === "screenshot";
  const busy = draw.isPending || remove.isPending || background.isPending || proofread.isPending;
  const locked = ["scheduled", "publishing", "published", "publish_unknown", "cancelled"].includes(post.status);

  function design(): Design {
    return {
      template,
      background_asset_id: needsPicture ? pictureId : null,
      // empty means "use the default": the pillar's name, the post's own headline
      kicker: kicker.trim() === "" ? null : kicker.trim(),
      headline: headline.trim() === "" ? null : headline.trim(),
      subline: subline.trim() === "" ? null : subline.trim(),
      credit: credit.trim() === "" ? null : credit.trim(),
      show_logo: showLogo,
      show_handle: true,
    };
  }

  function done(p: Post, text: string) {
    setMessage({ ok: true, text: p.approval_withdrawn ? `${text} The earlier approval was withdrawn.` : text });
  }

  function save() {
    setMessage(null);
    draw.mutate(
      { id: post!.id, design: design() },
      {
        onSuccess: (p) => done(p, p.artwork?.ok ? "Artwork made." : "Artwork made, but it needs attention (see below)."),
        onError: (e) => setMessage({ ok: false, text: errorMessage(e, "Couldn't make the artwork.") }),
      },
    );
  }

  function reject() {
    if (!window.confirm("Remove this artwork? The design is kept so you can change it and draw it again.")) return;
    setMessage(null);
    remove.mutate(post!.id, { onSuccess: (p) => done(p, "Artwork removed."), onError: (e) => setMessage({ ok: false, text: errorMessage(e, "Couldn't remove it.") }) });
  }

  function newBackground() {
    setMessage(null);
    background.mutate(
      { id: post!.id, design: design(), direction: direction.trim() },
      {
        onSuccess: (p) => {
          setPictureId(p.design?.background_asset_id ?? null);
          done(p, "New AI background made and the artwork redrawn. Only the picture changed.");
        },
        onError: (e) => setMessage({ ok: false, text: errorMessage(e, "Couldn't make a background.") }),
      },
    );
  }

  function check() {
    setProof(null);
    proofread.mutate(post!.id, {
      onSuccess: (r) => setProof(r),
      onError: (e) => setMessage({ ok: false, text: errorMessage(e, "Couldn't proofread.") }),
    });
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[92vh] max-w-4xl overflow-y-auto">
        <DialogHeader>
          <DialogTitle>Artwork: {post.title}</DialogTitle>
          <DialogDescription>
            The words and logo are drawn by code, exactly as written. AI is only ever used for an optional background.
          </DialogDescription>
        </DialogHeader>

        <div className="grid grid-cols-1 gap-6 lg:grid-cols-[1fr_320px]">
          <div className="space-y-4">
            <fieldset disabled={locked || busy} className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <div className="space-y-1.5 sm:col-span-2">
                <Label htmlFor="aw-template">Template</Label>
                <select id="aw-template" className={NATIVE_SELECT} value={template} onChange={(e) => setTemplate(e.target.value as Template)}>
                  {TEMPLATES.map((t) => (
                    <option key={t.value} value={t.value}>
                      {t.label}
                    </option>
                  ))}
                </select>
                <p className="text-xs text-muted-foreground">{TEMPLATES.find((t) => t.value === template)?.hint}</p>
              </div>

              {needsPicture && (
                <div className="space-y-2 sm:col-span-2">
                  <span className="text-sm font-medium">Picture</span>
                  {pictures.length === 0 ? (
                    <p className="text-xs text-muted-foreground">No pictures yet. Upload one in the Library tab{template === "photo" ? ", or make an AI background below" : ""}.</p>
                  ) : (
                    <div className="grid max-h-44 grid-cols-4 gap-2 overflow-y-auto sm:grid-cols-6">
                      {pictures.map((a) => (
                        <button
                          key={a.id}
                          type="button"
                          aria-pressed={pictureId === a.id}
                          aria-label={`Use ${a.filename}`}
                          onClick={() => setPictureId(a.id)}
                          className={`relative aspect-square overflow-hidden rounded border ${pictureId === a.id ? "ring-2 ring-primary" : ""}`}
                        >
                          {a.url && <img src={a.url} alt={a.alt_text || a.filename} className="h-full w-full object-cover" loading="lazy" />}
                          {a.synthetic && <span className="absolute left-0.5 top-0.5 rounded bg-black/70 px-1 text-[9px] text-white">AI</span>}
                        </button>
                      ))}
                    </div>
                  )}
                </div>
              )}

              <div className="space-y-1.5">
                <Label htmlFor="aw-kicker">Small label above the headline</Label>
                <Input id="aw-kicker" value={kicker} maxLength={40} placeholder="Default: the content pillar" onChange={(e) => setKicker(e.target.value)} />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="aw-headline">Headline on the cover</Label>
                <Input id="aw-headline" value={headline} maxLength={120} placeholder="Default: the post's headline" onChange={(e) => setHeadline(e.target.value)} />
              </div>
              <div className="space-y-1.5 sm:col-span-2">
                <Label htmlFor="aw-subline">Supporting line (optional)</Label>
                <Input id="aw-subline" value={subline} maxLength={160} onChange={(e) => setSubline(e.target.value)} />
              </div>
              {template === "screenshot" && (
                <div className="space-y-1.5 sm:col-span-2">
                  <Label htmlFor="aw-credit">Caption under the screenshot</Label>
                  <Input id="aw-credit" value={credit} maxLength={80} onChange={(e) => setCredit(e.target.value)} />
                </div>
              )}
              <label className="flex items-center gap-2 text-sm sm:col-span-2">
                <input type="checkbox" checked={showLogo} onChange={(e) => setShowLogo(e.target.checked)} />
                Show the approved logo
              </label>
              {template === "photo" && usage.data?.image_configured && (
                <div className="space-y-1.5 sm:col-span-2">
                  <Label htmlFor="aw-direction">AI background: direction (optional)</Label>
                  <div className="flex flex-wrap gap-2">
                    <Input id="aw-direction" className="min-w-0 flex-1" value={direction} maxLength={200} placeholder="e.g. soft paper texture, cool tones" onChange={(e) => setDirection(e.target.value)} />
                    <Button type="button" variant="outline" onClick={newBackground}>
                      {background.isPending ? "Making..." : "Make a new AI background"}
                    </Button>
                  </div>
                  <p className="text-xs text-muted-foreground">Only the picture changes. It is marked as AI-made and is never presented as a real photograph.</p>
                </div>
              )}
              {template === "photo" && usage.data && !usage.data.image_configured && (
                <p className="text-xs text-muted-foreground sm:col-span-2">AI backgrounds aren&apos;t set up on this server. Upload your own photo in the Library tab.</p>
              )}
            </fieldset>

            {locked && <p className="text-sm text-muted-foreground">This post is cancelled, scheduled or published, so its artwork can&apos;t be changed.</p>}

            <div className="flex flex-wrap gap-2">
              <Button onClick={save} disabled={locked || busy || (needsPicture && !pictureId)}>
                {draw.isPending ? "Drawing..." : files.length ? "Save and redraw" : "Save and draw"}
              </Button>
              {files.length > 0 && (
                <>
                  <Button variant="outline" onClick={check} disabled={busy}>
                    {proofread.isPending ? "Checking..." : "Proofread the words (AI)"}
                  </Button>
                  <Button variant="outline" onClick={() => setShowGrid((v) => !v)}>
                    {showGrid ? "Hide the grid" : "See it in the grid"}
                  </Button>
                  <Button variant="outline" onClick={reject} disabled={locked || busy}>
                    Remove this artwork
                  </Button>
                </>
              )}
            </div>
            {needsPicture && !pictureId && <p className="text-xs text-muted-foreground">Choose a picture to draw this template.</p>}
            {message && (
              <p role={message.ok ? "status" : "alert"} className={message.ok ? "text-sm text-emerald-700" : "text-sm text-destructive"}>
                {message.text}
              </p>
            )}
            {proof && (
              <div className="rounded-md border p-3 text-sm" role="status">
                {proof.ok ? (
                  "No spelling or grammar problems found in the words on the artwork."
                ) : (
                  <ul className="list-disc space-y-0.5 pl-5">
                    {proof.issues.map((i, n) => (
                      <li key={n}>
                        “{i.text}” → {i.suggestion}
                      </li>
                    ))}
                  </ul>
                )}
                <p className="mt-1 text-xs text-muted-foreground">Fix the wording in the post, then draw again.</p>
              </div>
            )}
            {showGrid && (
              <div className="rounded-md border p-3">
                <GridPreview postId={post.id} compact />
              </div>
            )}
          </div>

          <div className="space-y-3">
            {stale && (
              <p className="rounded-md border border-amber-300 bg-amber-50 p-2 text-sm text-amber-900">
                The words or design changed since this artwork was drawn. Draw it again so it matches.
              </p>
            )}
            {files.length === 0 ? (
              <div className="flex aspect-[4/5] items-center justify-center rounded-md border border-dashed p-4 text-center text-sm text-muted-foreground">
                No artwork yet. Choose a template and press &quot;Save and draw&quot;.
              </div>
            ) : (
              <div className="space-y-3">
                {files.map((f) => (
                  <div key={f.sha256} className="space-y-1.5">
                    {f.url ? (
                      <img src={f.url} alt={`Artwork${files.length > 1 ? `, slide ${f.slide + 1}` : ""}`} className="w-full rounded-md border" />
                    ) : (
                      <div className="flex aspect-[4/5] items-center justify-center rounded-md border text-xs text-muted-foreground">No preview</div>
                    )}
                    <div className="flex flex-wrap items-center gap-1.5 text-xs">
                      <Badge variant={f.validation.ok ? "success" : "destructive"}>{f.validation.ok ? "Meets the design rules" : "Needs attention"}</Badge>
                      <span className="text-muted-foreground">
                        {f.width}×{f.height}
                        {f.validation.min_contrast != null ? ` · contrast ${f.validation.min_contrast}:1` : ""}
                        {f.validation.min_font_px != null ? ` · smallest text ${f.validation.min_font_px}px` : ""}
                      </span>
                    </div>
                    {f.validation.problems.map((p) => (
                      <p key={p} className="text-xs text-destructive">
                        {p}
                      </p>
                    ))}
                    {f.validation.notes.map((n) => (
                      <p key={n} className="text-xs text-muted-foreground">
                        {n}
                      </p>
                    ))}
                  </div>
                ))}
                {post.artwork?.synthetic_background && <Badge variant="warning">AI-made background: not a real photograph</Badge>}
              </div>
            )}
          </div>
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Close
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
