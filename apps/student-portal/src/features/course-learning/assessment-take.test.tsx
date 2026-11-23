import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it } from "vitest";

import type { TakeState } from "@/features/course-learning/api/course-learning-api";
import { AssessmentTakePage } from "@/features/course-learning/pages/assessment-take-page";

function page(state: TakeState | undefined) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  if (state) client.setQueryData(["course-learning", "c1", "take", "a1"], state);
  return renderToStaticMarkup(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={["/courses/c1/assessments/a1"]}>
        <Routes>
          <Route path="/courses/:courseId/assessments/:assessmentId" element={<AssessmentTakePage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

const state: TakeState = {
  attempt_id: "t1",
  status: "in_progress",
  remaining_seconds: 125,
  saved_answers: {},
  questions: [
    { id: "q1", text: "Which port does HTTPS use?", marks: 2, allow_multiple: false, options: [{ index: 0, text: "80" }, { index: 1, text: "443" }] },
    { id: "q2", text: "Pick the encrypted protocols", marks: 3, allow_multiple: true, options: [{ index: 0, text: "SSH" }, { index: 1, text: "Telnet" }, { index: 2, text: "TLS" }] },
  ],
};

describe("taking an assessment", () => {
  it("shows every question with its marks, radio buttons for one answer and checkboxes for several", () => {
    const out = page(state);
    expect(out).toContain("1. Which port does HTTPS use?");
    expect(out).toContain("(2 marks)");
    expect(out).toContain("Choose every correct answer.");
    expect((out.match(/type="radio"/g) ?? []).length).toBe(2);
    expect((out.match(/type="checkbox"/g) ?? []).length).toBe(3);
  });

  it("offers a submit button and never anything that reveals an answer", () => {
    const out = page(state);
    expect(out).toContain("Submit answers");
    expect(out).not.toMatch(/correct_indices|is_correct|answer_key/);
  });

  it("is a clear refusal, not a quiz, when the server will not start it (revoked, not published, wrong internship)", () => {
    const out = page(undefined);
    expect(out).not.toContain("Submit answers");
  });
});
