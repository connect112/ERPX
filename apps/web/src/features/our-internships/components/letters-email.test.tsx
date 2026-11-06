import { QueryClient, QueryClientProvider, type UseQueryResult } from "@tanstack/react-query";
import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import type { EmailPreview, LetterConfig, LetterSettings } from "@/features/our-internships/api/letters-api";
import { LettersEmail } from "@/features/our-internships/components/letters-email";

const permissions = vi.hoisted(() => ({ canManage: true, canPublish: true, canUseStudents: true, loaded: true }));
vi.mock("@/features/email-studio/lib/permissions", () => ({ useStudioPermissions: () => permissions }));

const draft = { email: { subject: "Your offer", body: "Hello {{student_name}}" } } as unknown as LetterConfig;
const settings = { config: draft, placeholders: { student_name: "The student's name" } } as unknown as LetterSettings;

const base: EmailPreview = {
  to: "asha@example.com",
  subject: "Congratulations Asha",
  body: "plain text",
  attachment: "OfferLetter_Asha.pdf",
  html: "<html><body><p>Hi Asha</p></body></html>",
  source: "studio",
  template: { id: "t-1", name: "Offer with onboarding", version_number: 3, published_at: "2026-11-01T10:00:00Z" },
  uses_link: true,
  link_available: true,
  problem: null,
};

function draw(email: EmailPreview | undefined) {
  const preview = { data: email, isError: false, isFetching: false, refetch: () => Promise.resolve() } as unknown as UseQueryResult<EmailPreview>;
  return renderToStaticMarkup(
    <QueryClientProvider client={new QueryClient()}>
      <MemoryRouter>
        <LettersEmail internshipId="i-1" settings={settings} draft={draft} onDraft={() => undefined} dirty={false} rows={[]} preview={preview} previewFor="" onPreviewFor={() => undefined} />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("the offer letter email card", () => {
  it("shows the assigned published template, a way to manage it, and the server-drawn email in a sandboxed frame", () => {
    const html = draw(base);
    expect(html).toContain("Offer with onboarding");
    expect(html).toContain("Published v3");
    expect(html).toContain("Includes the student&#x27;s onboarding link");
    expect(html).toContain('href="/administration/email-templates/studio/t-1"');
    expect(html).toContain('sandbox=""');
    expect(html).toContain("Hi Asha");
    expect(html).toContain("The link in this preview is a sample that opens nothing.");
    expect(html).not.toContain("Built-in wording"); // the duplicate editor is gone while a template is assigned
    expect(html).not.toContain('id="em-subject"');
  });

  it("explains the legacy fallback and keeps its wording editable when no template is assigned", () => {
    const html = draw({ ...base, source: "legacy", template: null, uses_link: false });
    expect(html).toContain("No Email Studio template is assigned.");
    expect(html).toContain("Built-in wording");
    expect(html).toContain('id="em-subject"');
    expect(html).toContain('href="/administration/email-templates/create"');
  });

  it("reports an assigned template that cannot be used instead of hiding it", () => {
    const html = draw({ ...base, html: "", problem: "The template was deleted" });
    expect(html).toContain("This template cannot be used right now: The template was deleted");
    expect(html).not.toContain('title="Email preview"');
  });

  it("does not offer the Email Studio links to someone without access", () => {
    permissions.canManage = false;
    permissions.canPublish = false;
    const html = draw(base);
    permissions.canManage = true;
    permissions.canPublish = true;
    expect(html).not.toContain("/administration/email-templates");
    expect(html).toContain("Ask an administrator with Email Studio access");
  });

  it("says when the link is left out because onboarding is manual", () => {
    expect(draw({ ...base, link_available: false })).toContain("Link left out (manual onboarding)");
  });
});
