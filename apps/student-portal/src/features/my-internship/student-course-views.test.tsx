import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { EnrollmentListItem } from "@/features/dashboard/components/enrollment-list-item";
import type { MyInternship } from "@/features/my-internship/api/my-internship-api";
import { LearningCourse } from "@/features/my-internship/components/learning-course";
import { MyInternshipsPage } from "@/features/my-internship/pages/my-internships-page";

const list = vi.hoisted(() => ({ value: { data: undefined as unknown, isLoading: false, isError: false } }));
vi.mock("@/features/my-internship/api/my-internship-api", async (original) => ({
  ...(await original<object>()),
  useMyInternshipList: () => list.value,
}));
vi.mock("@/features/courses/api/courses-hooks", () => ({ useMyCourse: () => ({ data: { title: "DevSecOps Level-1" }, isLoading: false }) }));

const course = { id: "c1", title: "DevSecOps Level-1", level: "beginner", duration_hours: 40, accessible: true };
const internship = (over: Partial<MyInternship> = {}): MyInternship => ({
  id: "i1", selection_id: "s1", title: "DevSecOps Internship", description: null, status: "selecting", open_assignments: 0, open_exams: 0, lms_status: "granted", course, ...over,
});
const html = (node: React.ReactElement) => renderToStaticMarkup(<MemoryRouter>{node}</MemoryRouter>);

describe("the learning course on a student's internship", () => {
  it("shows the course apart from the internship, with a way to open it while the enrolment is live", () => {
    const out = html(<LearningCourse course={course} lmsStatus="granted" />);
    expect(out).toContain("Learning course");
    expect(out).toContain("DevSecOps Level-1");
    expect(out).toContain("Beginner · 40 hours");
    expect(out).toContain('href="/courses/c1"');
    expect(out).toContain("LMS access active");
  });

  it("offers no way in when the course cannot be opened, and says why when access was withdrawn", () => {
    expect(html(<LearningCourse course={{ ...course, accessible: false }} lmsStatus="granted" />)).not.toContain("href=");
    const withdrawn = html(<LearningCourse course={course} lmsStatus="revoked" />);
    expect(withdrawn).not.toContain("href=");
    expect(withdrawn).toContain("withdrawn");
  });

  it("shows nothing when no course is linked", () => {
    expect(html(<LearningCourse course={null} lmsStatus="granted" />)).toBe("");
  });
});

describe("My Internships", () => {
  beforeEach(() => {
    list.value = { data: undefined, isLoading: false, isError: false };
  });

  it("lists each internship with its own course and its status; a withdrawn one is not a link", () => {
    list.value.data = [internship(), internship({ id: "i2", title: "Cloud Internship", lms_status: "revoked", course: { ...course, id: "c2", title: "Cloud Basics", accessible: false } })];
    const out = html(<MyInternshipsPage />);
    expect(out).toContain("DevSecOps Internship");
    expect(out).toContain("Cloud Internship");
    expect(out).toContain("DevSecOps Level-1");
    expect(out).toContain("Cloud Basics");
    expect(out).toContain("Access withdrawn");
    expect(out).toContain('href="/my-internship/i1"');
    expect(out).not.toContain('href="/my-internship/i2"'); // nothing of a withdrawn internship opens
    expect(out).toContain('href="/courses/c1"'); // the way into the enrolled course
    expect(out).not.toContain('href="/courses/c2"');
  });

  it("opens a single granted internship straight away but keeps a single withdrawn one on the list with its status", () => {
    list.value.data = [internship()];
    expect(html(<MyInternshipsPage />)).not.toContain("Learning course"); // redirected, nothing rendered here
    list.value.data = [internship({ lms_status: "revoked", course: { ...course, accessible: false } })];
    const out = html(<MyInternshipsPage />);
    expect(out).toContain("Access withdrawn");
    expect(out).toContain("DevSecOps Internship");
  });

  it("copes with an internship that has no linked course", () => {
    list.value.data = [internship({ course: null }), internship({ id: "i3", title: "Second", course: null })];
    const out = html(<MyInternshipsPage />);
    expect(out).toContain("DevSecOps Internship");
    expect(out).not.toContain("Learning course");
  });
});

describe("My Courses", () => {
  const enrollment = (internships?: { id: string; title: string }[]) => ({ id: "e1", student_id: "s", course_id: "c1", enrolled_on: "2026-11-10", status: "active" as const, created_at: "", internships });

  it("names the student's own internships next to the course, however many there are", () => {
    const out = html(<EnrollmentListItem enrollment={enrollment([{ id: "i1", title: "DevSecOps Internship" }, { id: "i2", title: "Cloud Internship" }])} />);
    expect(out).toContain("DevSecOps Level-1");
    expect(out).toContain("Internship: DevSecOps Internship, Cloud Internship");
  });

  it("leaves an ordinary course exactly as it was", () => {
    for (const none of [undefined, []]) {
      const out = html(<EnrollmentListItem enrollment={enrollment(none)} />);
      expect(out).toContain("DevSecOps Level-1");
      expect(out).not.toContain("Internship:");
    }
  });
});
