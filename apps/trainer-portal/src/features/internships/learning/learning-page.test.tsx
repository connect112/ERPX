import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it } from "vitest";

import { type LearningContext, key } from "@/features/internships/learning/api";
import { InternshipLearningPage } from "@/features/internships/learning/internship-learning-page";

const TABS = ["Curriculum", "Enrollments", "Evaluations", "Projects", "Discussions", "Practicals", "Viva"].map((label) => ({ key: label.toLowerCase(), label }));

function render(ctx: LearningContext | undefined) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  if (ctx) client.setQueryData(key("context", "i1"), ctx);
  return renderToStaticMarkup(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={["/internships/i1"]}>
        <Routes>
          <Route path="/internships/:internshipId" element={<InternshipLearningPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

const context = (over: Partial<LearningContext["internships"][0]> = {}): LearningContext => ({
  tabs: TABS,
  course: { id: "c1", title: "DevSecOps Level-1", course_type: "internship", is_published: true },
  internships: [{ id: "i1", title: "Pentrix Cyber Internship", status: "selecting", can_view: true, can_manage: true, can_delete: false, ...over }],
  course_caps: {},
});

describe("an instructor's Learning page in the trainer portal", () => {
  it("shows the same seven tabs, in order, for their internship", () => {
    const out = render(context());
    const positions = TABS.map((t) => out.indexOf(`>${t.label}<`));
    expect(positions.every((p) => p > 0)).toBe(true);
    expect([...positions].sort((a, b) => a - b)).toEqual(positions);
    expect(out).toContain("Pentrix Cyber Internship");
    expect(out).toContain("DevSecOps Level-1");
  });

  it("says plainly that they can add, edit and mark but not delete", () => {
    expect(render(context())).toContain("You can add, edit, mark and review, but not delete.");
  });

  it("offers a way back to their internships", () => {
    expect(render(context())).toContain('href="/internships"');
  });

  it("shows a loading state, not a broken page, before the context arrives", () => {
    const out = render(undefined);
    expect(out).not.toContain("trainer-learning");
    expect(out).not.toContain("learning-denied");
  });
});
