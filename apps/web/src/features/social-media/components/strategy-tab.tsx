import { Plus, Trash2 } from "lucide-react";
import { useEffect, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { Textarea } from "@/components/ui/textarea";
import { useMyRoles } from "@/features/auth/api/authorization-hooks";
import type { Brand, DesignRules, Persona, Pillar, SocialSettings } from "@/features/social-media/api/social-media-api";
import { useSocialSettings, useUpdateSocialSettings } from "@/features/social-media/api/social-media-hooks";
import { errorMessage } from "@/features/social-media/lib/format";

const COLOR_KEYS = ["background", "ink", "primary", "accent", "muted"] as const;

function lines(text: string): string[] {
  return text.split("\n").map((l) => l.trim()).filter(Boolean);
}

function slug(label: string, taken: string[]): string {
  const base = label.toLowerCase().replace(/[^a-z0-9]+/g, "_").replace(/^_+|_+$/g, "").slice(0, 30) || "pillar";
  let key = /^[a-z]/.test(base) ? base : `p_${base}`;
  let n = 2;
  while (taken.includes(key)) key = `${base}_${n++}`;
  return key.length < 2 ? `${key}_x` : key;
}

/** Brand, voice, content pillars, audience personas, prohibited claims, objectives and the design rules artwork must follow. */
export function StrategyTab() {
  const query = useSocialSettings();
  const update = useUpdateSocialSettings();
  const me = useMyRoles();
  const canManage = (me.data?.is_superuser ?? false) || (me.data?.effective_permissions ?? []).includes("social_media.manage");

  const [brand, setBrand] = useState<Brand | null>(null);
  const [pillars, setPillars] = useState<Pillar[]>([]);
  const [personas, setPersonas] = useState<Persona[]>([]);
  const [claims, setClaims] = useState("");
  const [objectives, setObjectives] = useState("");
  const [rules, setRules] = useState<DesignRules | null>(null);
  const [forbidden, setForbidden] = useState("");
  const [prefer, setPrefer] = useState("");
  const [message, setMessage] = useState<{ ok: boolean; text: string } | null>(null);

  const data: SocialSettings | undefined = query.data;
  useEffect(() => {
    if (!data) return;
    setBrand(data.brand);
    setPillars(data.pillars);
    setPersonas(data.personas);
    setClaims(data.prohibited_claims.join("\n"));
    setObjectives(data.objectives.join("\n"));
    setRules(data.design_rules);
    setForbidden(data.design_rules.forbidden_visuals.join("\n"));
    setPrefer(data.design_rules.prefer.join("\n"));
  }, [data]);

  if (query.isLoading || !brand || !rules) return <Skeleton className="h-64 w-full" />;
  if (query.isError) return <p className="text-sm text-destructive">Couldn&apos;t load the strategy.</p>;

  const total = pillars.filter((p) => p.enabled).reduce((sum, p) => sum + p.share, 0);

  function save() {
    setMessage(null);
    update.mutate(
      {
        brand: brand ?? undefined,
        pillars,
        personas,
        prohibited_claims: lines(claims),
        objectives: lines(objectives),
        design_rules: rules ? { ...rules, forbidden_visuals: lines(forbidden), prefer: lines(prefer) } : undefined,
      },
      {
        onSuccess: () => setMessage({ ok: true, text: "Strategy saved." }),
        onError: (e) => setMessage({ ok: false, text: errorMessage(e, "Couldn't save the strategy.") }),
      },
    );
  }

  const setColor = (key: (typeof COLOR_KEYS)[number], value: string) =>
    setBrand({ ...brand, colors: { ...brand.colors, [key]: value }, colors_confirmed: false });

  return (
    <fieldset disabled={!canManage} className="space-y-6">
      {!canManage && <p className="text-sm text-muted-foreground">You can view the strategy. Changing it needs the social_media.manage permission.</p>}

      <Card>
        <CardHeader>
          <CardTitle>Brand</CardTitle>
          <CardDescription>Used by the content studio and artwork renderer in the next phase.</CardDescription>
        </CardHeader>
        <CardContent className="grid gap-4 sm:grid-cols-2">
          <div className="space-y-1.5">
            <Label htmlFor="b-name">Brand name</Label>
            <Input id="b-name" value={brand.name} onChange={(e) => setBrand({ ...brand, name: e.target.value })} />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="b-tag">Tagline</Label>
            <Input id="b-tag" value={brand.tagline} onChange={(e) => setBrand({ ...brand, tagline: e.target.value })} />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="b-handle">Instagram handle</Label>
            <Input id="b-handle" value={brand.handle} placeholder="@yourhandle" onChange={(e) => setBrand({ ...brand, handle: e.target.value })} />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="b-web">Website</Label>
            <Input id="b-web" value={brand.website} placeholder="https://" onChange={(e) => setBrand({ ...brand, website: e.target.value })} />
          </div>
          <div className="space-y-1.5 sm:col-span-2">
            <Label htmlFor="b-voice">Brand voice</Label>
            <Textarea id="b-voice" rows={3} value={brand.voice} onChange={(e) => setBrand({ ...brand, voice: e.target.value })} />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="b-hfont">Heading font</Label>
            <Input id="b-hfont" value={brand.fonts.heading} onChange={(e) => setBrand({ ...brand, fonts: { ...brand.fonts, heading: e.target.value } })} />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="b-bfont">Body font</Label>
            <Input id="b-bfont" value={brand.fonts.body} onChange={(e) => setBrand({ ...brand, fonts: { ...brand.fonts, body: e.target.value } })} />
          </div>
          <div className="space-y-2 sm:col-span-2">
            <div className="flex items-center gap-2">
              <span className="text-sm font-medium">Colours</span>
              {brand.colors_confirmed ? <Badge variant="success">Confirmed</Badge> : <Badge variant="warning">Placeholders: not confirmed</Badge>}
            </div>
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-5">
              {COLOR_KEYS.map((key) => (
                <div key={key} className="space-y-1">
                  <span className="text-xs capitalize text-muted-foreground">{key}</span>
                  <div className="flex items-center gap-2">
                    <input
                      type="color"
                      aria-label={`${key} colour`}
                      value={brand.colors[key]}
                      onChange={(e) => setColor(key, e.target.value)}
                      className="h-9 w-9 cursor-pointer rounded border"
                    />
                    <span className="font-mono text-xs">{brand.colors[key]}</span>
                  </div>
                </div>
              ))}
            </div>
            <label className="flex items-center gap-2 text-sm">
              <input type="checkbox" checked={brand.colors_confirmed} onChange={(e) => setBrand({ ...brand, colors_confirmed: e.target.checked })} />
              These are our approved brand colours
            </label>
          </div>
          <p className="text-sm text-muted-foreground sm:col-span-2">
            {brand.logo_key
              ? "An approved logo is set. Change it in the Library tab."
              : "No approved logo yet. Upload it in the Library tab: the exact file is used and never redrawn."}
          </p>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Content pillars</CardTitle>
          <CardDescription>
            The share is how much of your posting each topic should get. Enabled pillars add up to {total}% (at most 100%).
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          {pillars.map((pillar, index) => (
            <div key={pillar.key} className="grid items-center gap-2 rounded-md border p-3 sm:grid-cols-[auto_1fr_5rem_auto]">
              <input
                type="checkbox"
                aria-label={`Enable ${pillar.label}`}
                checked={pillar.enabled}
                onChange={(e) => setPillars(pillars.map((p, i) => (i === index ? { ...p, enabled: e.target.checked } : p)))}
              />
              <div className="space-y-1">
                <Input
                  aria-label="Pillar name"
                  value={pillar.label}
                  maxLength={120}
                  onChange={(e) => setPillars(pillars.map((p, i) => (i === index ? { ...p, label: e.target.value } : p)))}
                />
                <Input
                  aria-label="Pillar description"
                  className="text-xs"
                  value={pillar.description}
                  maxLength={300}
                  onChange={(e) => setPillars(pillars.map((p, i) => (i === index ? { ...p, description: e.target.value } : p)))}
                />
              </div>
              <div className="flex items-center gap-1">
                <Input
                  aria-label="Share in percent"
                  type="number"
                  min={0}
                  max={100}
                  value={pillar.share}
                  onChange={(e) => setPillars(pillars.map((p, i) => (i === index ? { ...p, share: Math.max(0, Math.min(100, Number(e.target.value) || 0)) } : p)))}
                />
                <span className="text-sm">%</span>
              </div>
              <Button type="button" size="icon" variant="ghost" aria-label={`Remove ${pillar.label}`} onClick={() => setPillars(pillars.filter((_, i) => i !== index))}>
                <Trash2 className="h-4 w-4" />
              </Button>
            </div>
          ))}
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={() => setPillars([...pillars, { key: slug("new pillar", pillars.map((p) => p.key)), label: "New pillar", description: "", share: 0, enabled: true }])}
          >
            <Plus className="mr-1 h-4 w-4" /> Add pillar
          </Button>
          {total > 100 && <p className="text-sm text-destructive">The enabled shares add up to more than 100%.</p>}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Audience personas</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          {personas.map((persona, index) => (
            <div key={persona.key} className="grid items-start gap-2 rounded-md border p-3 sm:grid-cols-[1fr_2fr_auto]">
              <Input
                aria-label="Persona name"
                value={persona.label}
                maxLength={120}
                onChange={(e) => setPersonas(personas.map((p, i) => (i === index ? { ...p, label: e.target.value } : p)))}
              />
              <Textarea
                aria-label="Persona description"
                rows={2}
                value={persona.description}
                maxLength={400}
                onChange={(e) => setPersonas(personas.map((p, i) => (i === index ? { ...p, description: e.target.value } : p)))}
              />
              <Button type="button" size="icon" variant="ghost" aria-label={`Remove ${persona.label}`} onClick={() => setPersonas(personas.filter((_, i) => i !== index))}>
                <Trash2 className="h-4 w-4" />
              </Button>
            </div>
          ))}
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={() => setPersonas([...personas, { key: slug("persona", personas.map((p) => p.key)), label: "New persona", description: "" }])}
          >
            <Plus className="mr-1 h-4 w-4" /> Add persona
          </Button>
        </CardContent>
      </Card>

      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Claims we never make</CardTitle>
            <CardDescription>One per line. Drafts are checked against this list by the content studio.</CardDescription>
          </CardHeader>
          <CardContent>
            <Textarea aria-label="Prohibited claims" rows={8} value={claims} onChange={(e) => setClaims(e.target.value)} />
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>Content objectives</CardTitle>
            <CardDescription>One per line.</CardDescription>
          </CardHeader>
          <CardContent>
            <Textarea aria-label="Content objectives" rows={8} value={objectives} onChange={(e) => setObjectives(e.target.value)} />
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Design rules</CardTitle>
          <CardDescription>
            Limits the artwork renderer and the profile-grid check enforce. They exist to keep the profile clean and uncluttered.
          </CardDescription>
        </CardHeader>
        <CardContent className="grid gap-4 sm:grid-cols-2">
          <div className="space-y-1.5">
            <Label htmlFor="r-words">Most words in a cover headline</Label>
            <Input id="r-words" type="number" min={1} max={20} value={rules.max_headline_words} onChange={(e) => setRules({ ...rules, max_headline_words: Number(e.target.value) || 1 })} />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="r-chars">Most characters of text on a cover</Label>
            <Input id="r-chars" type="number" min={10} max={300} value={rules.max_cover_text_chars} onChange={(e) => setRules({ ...rules, max_cover_text_chars: Number(e.target.value) || 10 })} />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="r-fonts">Most fonts on one design</Label>
            <Input id="r-fonts" type="number" min={1} max={3} value={rules.max_fonts} onChange={(e) => setRules({ ...rules, max_fonts: Number(e.target.value) || 1 })} />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="r-contrast">Lowest text contrast ratio</Label>
            <Input id="r-contrast" type="number" min={3} max={21} step={0.5} value={rules.min_contrast_ratio} onChange={(e) => setRules({ ...rules, min_contrast_ratio: Number(e.target.value) || 3 })} />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="r-forbid">Never use (one per line)</Label>
            <Textarea id="r-forbid" rows={7} value={forbidden} onChange={(e) => setForbidden(e.target.value)} />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="r-prefer">Prefer (one per line)</Label>
            <Textarea id="r-prefer" rows={7} value={prefer} onChange={(e) => setPrefer(e.target.value)} />
          </div>
        </CardContent>
      </Card>

      {canManage && (
        <div className="flex items-center gap-3">
          <Button type="button" onClick={save} disabled={update.isPending}>
            {update.isPending ? "Saving..." : "Save strategy"}
          </Button>
          {message && (
            <span role="status" className={message.ok ? "text-sm text-emerald-700" : "text-sm text-destructive"}>
              {message.text}
            </span>
          )}
        </div>
      )}
    </fieldset>
  );
}
