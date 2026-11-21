import { expect, test } from "@playwright/test";

import { type CoursesMock, mockCourses } from "./support/courses-mock";

/**
 * The shared Learning workspace in a real browser on the production build: the LMS course page and the internship page show exactly the
 * same seven tabs in the same order (and the old top-level Assignments / Assessments / Exams tabs are gone), old deep links still land on
 * the right content, a course shared by two internships asks which one you mean, and an instructor is not offered deleting or curriculum
 * editing. Only the server is replaced.
 */

const SEVEN = ["Curriculum", "Enrollments", "Evaluations", "Projects", "Discussions", "Practicals", "Viva"];

let mock: CoursesMock;
let problems: string[];

test.beforeEach(async ({ page }) => {
  problems = [];
  page.on("pageerror", (e) => problems.push(`pageerror: ${e.message}`));
  mock = await mockCourses(page);
  // int-1 and int-2 both use "Old Internship Course", so that course has two cohorts
  mock.internships.find((i) => i.id === "int-1")!.lms_course_id = "c-old";
});
test.afterEach(() => {
  expect(mock.unhandled, "the page asked for an API the test does not stub").toEqual([]);
  expect(problems).toEqual([]);
});

const tabLabels = async (page: import("@playwright/test").Page) =>
  page.getByTestId("learning-workspace").getByRole("tab").evaluateAll((els) => els.map((e) => (e.textContent ?? "").trim()).filter((t) => ["Curriculum", "Enrollments", "Evaluations", "Projects", "Discussions", "Practicals", "Viva"].includes(t)));

test("the LMS course page shows the seven learning tabs in order and no separate Assignments, Assessments or Exams tab", async ({ page }) => {
  await page.goto("/courses/c-old");
  await expect(page.getByTestId("learning-workspace")).toBeVisible();
  expect(await tabLabels(page)).toEqual(SEVEN);
  for (const gone of ["Assignments", "Assessments", "Exams"]) await expect(page.getByRole("tab", { name: gone, exact: true })).toHaveCount(0);
});

test("the internship page's Learning tab shows the very same seven tabs", async ({ page }) => {
  await page.goto("/our-internships/int-2");
  await page.getByTestId("internship-tab-learning").click();
  await expect(page.getByTestId("learning-workspace")).toBeVisible();
  expect(await tabLabels(page)).toEqual(SEVEN);
  // the page's own tabs stay
  for (const kept of ["Students", "Selected", "Learning"]) await expect(page.getByRole("tab", { name: kept }).first()).toBeVisible();
});

test("a course shared by two internships asks which one, and never shows internship-owned data until one is chosen", async ({ page }) => {
  await page.goto("/courses/c-old");
  const selector = page.getByTestId("cohort-selector");
  await expect(selector).toBeVisible();
  await expect(selector.getByRole("combobox")).toHaveValue("");
  await expect(selector.getByRole("combobox").locator("option")).toHaveText(["Choose an internship…", "DevSecOps Internship", "Cloud Internship"]);
  await page.getByTestId("learning-tab-enrollments").click();
  await expect(page.getByText("Choose an internship above to see its students and their LMS access.")).toBeVisible();
  await selector.getByRole("combobox").selectOption("int-1");
  await expect(selector).toContainText("Showing this internship's own activities");
});

test("old links still land on the right content", async ({ page }) => {
  await page.goto("/courses/c-old?tab=assignments");
  await expect(page.getByTestId("learning-tab-evaluations")).toHaveAttribute("data-state", "active");
  await page.goto("/our-internships/int-2?tab=exams");
  await expect(page.getByTestId("internship-tab-learning")).toHaveAttribute("data-state", "active");
  await expect(page.getByTestId("learning-tab-evaluations")).toHaveAttribute("data-state", "active");
  await page.goto("/our-internships/int-2?tab=projects");
  await expect(page.getByTestId("learning-tab-projects")).toHaveAttribute("data-state", "active");
  await page.goto("/courses/c-old?tab=viva");
  await expect(page.getByTestId("learning-tab-viva")).toHaveAttribute("data-state", "active");
});

test("a revoked student stays in the enrollments, marked, and independent access is labelled as such", async ({ page }) => {
  mock.learning.roster = [
    { selection_id: "s1", name: "Asha Rao", lms_status: "granted", provenance: "internship" },
    { selection_id: "s2", name: "Meera Iyer", lms_status: "revoked", provenance: "internship" },
    { selection_id: "s3", name: "Ravi Kumar", lms_status: "granted", provenance: "independent" },
  ];
  await page.goto("/our-internships/int-2?tab=learning");
  await page.getByTestId("learning-tab-enrollments").click();
  await expect(page.getByRole("row", { name: /Asha Rao/ })).toBeVisible();
  const meera = page.getByRole("row", { name: /Meera Iyer/ });
  await expect(meera).toBeVisible(); // history is kept
  await expect(meera).toContainText(/revoked/i);
  await expect(page.getByRole("row", { name: /Ravi Kumar/ })).toContainText(/independent/i);
});

test("an instructor can read the curriculum but is offered no way to edit or delete it", async ({ page }) => {
  mock.learning.instructor = true;
  await page.goto("/our-internships/int-2?tab=learning");
  await expect(page.getByTestId("learning-workspace")).toBeVisible();
  const workspace = page.getByTestId("learning-workspace");
  await expect(workspace.getByRole("button", { name: /Add chapter|New chapter/i })).toHaveCount(0);
  await expect(workspace.getByRole("button", { name: /Delete/i })).toHaveCount(0);
});

test("on a course that serves an internship, course-wide exams and assignments are tucked away and labelled; a regular course is unchanged", async ({ page }) => {
  await page.goto("/courses/c-old?tab=evaluations");
  await page.getByTestId("cohort-selector").getByRole("combobox").selectOption("int-1");
  // the internship's own section is the working one; the course-wide one is closed, with a warning that it is not an internship activity
  await expect(page.getByTestId("internship-exams")).toBeVisible();
  const wide = page.getByTestId("course-exams");
  await expect(wide).toContainText("course-wide, not part of any internship");
  await expect(wide.locator("details, summary").first()).toBeAttached();
  expect(await wide.evaluate((el) => el.tagName === "DETAILS" && !(el as HTMLDetailsElement).open)).toBe(true);
  await wide.locator("summary").click();
  await expect(wide).toContainText("not an internship activity");
  // a regular course has no internship: its exams are shown as before, not hidden
  await page.goto("/courses/c-py?tab=evaluations");
  const regular = page.getByTestId("course-exams");
  await expect(regular).toBeVisible();
  await expect(regular).not.toContainText("not part of any internship");
  expect(await regular.evaluate((el) => el.tagName)).toBe("SECTION");
});
