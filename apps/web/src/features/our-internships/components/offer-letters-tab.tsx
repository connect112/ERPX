import { useEffect, useState } from "react";

import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { type LetterConfig, useLetterSettings } from "@/features/our-internships/api/letters-api";
import { LettersConfig } from "@/features/our-internships/components/letters-config";
import { LettersGenerate, LettersList } from "@/features/our-internships/components/letters-generate";
import { LettersPreview } from "@/features/our-internships/components/letters-preview";
import { LettersRelease } from "@/features/our-internships/components/letters-release";
import { configChanged } from "@/features/our-internships/lib/letters";

/**
 * Offer letters of an internship, in the order they are done: set up the design once, preview and approve it, generate a
 * letter for every selected student, look them over, then release the approved ones by email. The settings being edited
 * live here, so the preview shows them before they are saved.
 */
export function OfferLettersTab({ internshipId }: { internshipId: string }) {
  const settings = useLetterSettings(internshipId);
  const [tab, setTab] = useState("config");
  const [draft, setDraft] = useState<LetterConfig | null>(null);
  const saved = settings.data?.config ?? null;
  const savedKey = saved ? JSON.stringify(saved) : "";

  // a new saved version (after Save, or a refresh) becomes the thing being edited
  useEffect(() => {
    if (saved) setDraft(saved);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [savedKey]);

  if (settings.isLoading || !draft) return <Skeleton className="h-64 w-full" />;
  if (settings.isError || !settings.data) return <p className="text-sm text-destructive">Could not load the offer letter settings.</p>;
  const s = settings.data;
  const dirty = configChanged(draft, saved);

  return (
    <Tabs value={tab} onValueChange={setTab} className="space-y-4">
      <TabsList className="h-auto flex-wrap">
        <TabsTrigger value="config">1. Configuration</TabsTrigger>
        <TabsTrigger value="preview">2. Design preview</TabsTrigger>
        <TabsTrigger value="generate">3. Generate</TabsTrigger>
        <TabsTrigger value="letters">4. Generated letters</TabsTrigger>
        <TabsTrigger value="release">5. Release</TabsTrigger>
      </TabsList>
      <TabsContent value="config">
        <LettersConfig internshipId={internshipId} settings={s} draft={draft} onDraft={setDraft} dirty={dirty} />
      </TabsContent>
      <TabsContent value="preview">
        <LettersPreview internshipId={internshipId} settings={s} draft={draft} dirty={dirty} />
      </TabsContent>
      <TabsContent value="generate">
        <LettersGenerate internshipId={internshipId} settings={s} onGo={setTab} />
      </TabsContent>
      <TabsContent value="letters">
        <LettersList internshipId={internshipId} settings={s} onGo={setTab} />
      </TabsContent>
      <TabsContent value="release">
        <LettersRelease internshipId={internshipId} settings={s} draft={draft} onDraft={setDraft} dirty={dirty} />
      </TabsContent>
    </Tabs>
  );
}
