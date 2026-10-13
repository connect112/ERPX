import { describe, expect, it } from "vitest";

import { CONTACT_EMAIL, DATA_DELETION, DELETION_DAYS, PRIVACY_POLICY, type LegalDocument } from "@/features/legal/lib/legal-content";

const text = (doc: LegalDocument) => [doc.title, doc.intro, ...doc.sections.flatMap((s) => [s.heading, ...(s.paragraphs ?? []), ...(s.items ?? [])])].join(" | ");

describe("legal pages", () => {
  it("say what the Instagram integration really handles", () => {
    const policy = text(PRIVACY_POLICY);
    for (const needle of ["comments and direct messages", "AI service", "do not sell", "retention period", "encrypted", "Apps and websites"]) {
      expect(policy.toLowerCase()).toContain(needle.toLowerCase());
    }
  });

  it("give a way to ask for deletion and a time limit", () => {
    const deletion = text(DATA_DELETION);
    expect(deletion).toContain(CONTACT_EMAIL);
    expect(deletion).toContain(`${DELETION_DAYS} days`);
    expect(text(PRIVACY_POLICY)).toContain("/data-deletion");
  });

  it("have no leftover placeholders", () => {
    for (const doc of [PRIVACY_POLICY, DATA_DELETION]) {
      expect(text(doc)).not.toMatch(/TODO|TBD|lorem|\[.*\]|your company/i);
      expect(doc.sections.length).toBeGreaterThan(3);
    }
  });
});
