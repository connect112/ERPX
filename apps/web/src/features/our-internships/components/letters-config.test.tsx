import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { CoursePlaceholderHint } from "@/features/our-internships/components/letters-config";

const draw = (placeholders: Record<string, string>) => renderToStaticMarkup(<CoursePlaceholderHint settings={{ placeholders }} />);

describe("the Offer Letter Designer's course placeholder", () => {
  it("tells staff the LMS course name can be printed, and that it is blank when no course is linked", () => {
    const html = draw({ student_name: "The student's name", lms_course_name: "The LMS course linked to the internship" });
    expect(html).toContain('data-testid="course-placeholder-hint"');
    expect(html).toContain("{{lms_course_name}}");
    expect(html).toContain("left blank when none is linked");
  });

  it("says nothing when the server does not offer the placeholder (an older server)", () => {
    expect(draw({ student_name: "The student's name" })).toBe("");
  });

  it("does not mix up the programme name with the course name", () => {
    const html = draw({ internship_name: "The internship's title", lms_course_name: "The LMS course" });
    expect(html).toContain("{{lms_course_name}}");
    expect(html).not.toContain("{{internship_name}}");
  });
});
