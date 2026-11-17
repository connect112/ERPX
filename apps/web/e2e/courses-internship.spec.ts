import { type Page, expect, test } from "@playwright/test";

import { type CoursesMock, mockCourses } from "./support/courses-mock";

/**
 * Regular and internship courses in a real browser on the production build: creating each kind, Show Fee / Hide Fee, linking an
 * internship while creating or later, the warnings before replacing a course, the partial result when linking fails, and creating an
 * internship course from an internship's own LMS course section and coming back to it. Only the server is replaced.
 */

let mock: CoursesMock;
let problems: string[];

test.beforeEach(async ({ page }) => {
  problems = [];
  page.on("pageerror", (e) => problems.push(`pageerror: ${e.message}`));
  mock = await mockCourses(page);
});
test.afterEach(() => {
  expect(mock.unhandled, "the page asked for an API the test does not stub").toEqual([]);
  expect(problems).toEqual([]);
});

async function newCourse(page: Page) {
  await page.goto("/courses");
  await expect(page.getByRole("heading", { name: "Courses" })).toBeVisible();
  await page.getByRole("button", { name: "New Course" }).click();
  await expect(page.getByRole("dialog")).toBeVisible();
}
const fill = async (page: Page, title: string, slug: string) => {
  await page.getByLabel("Title").fill(title);
  await page.getByLabel("Slug").fill(slug);
};

test("a regular course is created as before, with its own price", async ({ page }) => {
  await newCourse(page);
  await expect(page.getByRole("dialog").getByLabel("Course type", { exact: true })).toHaveValue("regular");
  await expect(page.getByLabel("Price")).toBeVisible();
  await expect(page.getByLabel("Fee visibility")).toHaveCount(0);
  await expect(page.getByLabel("Internship", { exact: true })).toHaveCount(0);
  await fill(page, "Linux Basics", "linux-basics");
  await page.getByLabel("Price").fill("2500");
  await page.getByRole("button", { name: "Create course" }).click();
  await expect(page.getByRole("dialog")).toBeHidden();
  expect(mock.created[0]).toMatchObject({ title: "Linux Basics", course_type: "regular", price: 2500, show_internship_fee: false });
  const row = page.getByRole("row", { name: /Linux Basics/ });
  await expect(row).toContainText("Regular Course");
  await expect(row).toContainText("₹2500");
});

test("an internship course has no price field and hides the fee by default", async ({ page }) => {
  await newCourse(page);
  await page.getByRole("dialog").getByLabel("Course type", { exact: true }).selectOption("internship");
  await expect(page.getByLabel("Price")).toHaveCount(0); // no independent course price
  await expect(page.getByLabel("Fee visibility")).toHaveValue("hide");
  await fill(page, "DevSecOps Level-1", "devsecops-level-1");
  await page.getByRole("button", { name: "Create course" }).click();
  await expect(page.getByRole("dialog")).toBeHidden();
  expect(mock.created[0]).toMatchObject({ title: "DevSecOps Level-1", course_type: "internship", price: 0, show_internship_fee: false });
  expect(mock.links).toEqual([]); // creating a course links nothing and enrols nobody unless an internship was chosen
  const row = page.getByRole("row", { name: /DevSecOps Level-1/ });
  await expect(row).toContainText("Internship Course");
  await expect(row).toContainText("Not linked to an internship");
  await expect(row).not.toContainText(/Free|₹0/);
});

test("Show Fee is stored, and the list and the course page show the linked internship's own fee, never a price", async ({ page }) => {
  await newCourse(page);
  await page.getByRole("dialog").getByLabel("Course type", { exact: true }).selectOption("internship");
  await page.getByLabel("Fee visibility").selectOption("show");
  await fill(page, "Fee Course", "fee-course");
  await page.getByLabel("Internship", { exact: true }).selectOption("int-1");
  await page.getByRole("button", { name: "Create course" }).click();
  await expect(page).toHaveURL(/\/courses\/c-new-1$/); // linked, so it opens the course
  expect(mock.created[0]).toMatchObject({ course_type: "internship", show_internship_fee: true, price: 0 });
  await expect(page.getByText("Fee: ₹5,900.00 (includes GST ₹900.00)")).toBeVisible();
  await expect(page.getByText("Price", { exact: true })).toHaveCount(0);
  await page.goto("/courses");
  await expect(page.getByRole("row", { name: /Fee Course/ })).toContainText("₹5,900.00");
});

test("Hide Fee shows no fee anywhere, even when linked to an internship with a fee", async ({ page }) => {
  await page.goto("/courses/c-hidden");
  await expect(page.getByRole("heading", { name: "Cloud Internship Course" })).toBeVisible();
  await expect(page.getByText("Not linked to an internship").first()).toBeVisible();
  await page.getByLabel("Link to an internship").selectOption("int-1");
  await page.getByRole("button", { name: "Link", exact: true }).click();
  await expect(page.getByRole("link", { name: "DevSecOps Internship" })).toBeVisible();
  await expect(page.getByText(/Fee:/)).toHaveCount(0);
  await expect(page.getByText(/Free|₹0/)).toHaveCount(0);
});

test("creating with an internship links it; replacing another course needs an explicit confirmation", async ({ page }) => {
  await newCourse(page);
  await page.getByRole("dialog").getByLabel("Course type", { exact: true }).selectOption("internship");
  await fill(page, "Replacement", "replacement");
  const picker = page.getByLabel("Internship", { exact: true });
  await expect(picker.locator("option")).toHaveText(["Do not link to an internship now", "DevSecOps Internship", 'Cloud Internship (uses "Old Internship Course")']); // closed ones are not offered
  await picker.selectOption("int-2");
  await expect(page.getByText("This internship already uses")).toContainText("Old Internship Course");
  await expect(page.getByRole("button", { name: "Create course" })).toBeDisabled(); // not until the replacement is confirmed
  await page.getByRole("checkbox").check();
  await page.getByRole("button", { name: "Create course" }).click();
  await expect(page).toHaveURL(/\/courses\/c-new-1$/);
  expect(mock.links).toEqual([{ internship: "int-2", course: "c-new-1", confirm: true }]);
});

test("if linking fails the course is still reported as created, with the reason and a way to open it", async ({ page }) => {
  mock.failNextLink = true;
  await newCourse(page);
  await page.getByRole("dialog").getByLabel("Course type", { exact: true }).selectOption("internship");
  await fill(page, "Orphan", "orphan");
  await page.getByLabel("Internship", { exact: true }).selectOption("int-1");
  await page.getByRole("button", { name: "Create course" }).click();
  const alert = page.getByRole("alert");
  await expect(alert).toContainText("The course was created, but it was not linked");
  await expect(alert).toContainText("The course cannot be changed while students are enrolled");
  expect(mock.courses.some((c) => c.title === "Orphan")).toBe(true);
  await page.getByRole("button", { name: "Open the course" }).click();
  await expect(page).toHaveURL(/\/courses\/c-new-1$/);
  await expect(page.getByText("Not linked to an internship").first()).toBeVisible();
});

test("the list filters by course type", async ({ page }) => {
  await page.goto("/courses");
  await expect(page.getByRole("row", { name: /Python Basics/ })).toBeVisible();
  await page.getByRole("combobox", { name: "Filter by course type" }).click();
  await page.getByRole("option", { name: "Internship Course" }).click();
  await expect(page.getByRole("row", { name: /Python Basics/ })).toHaveCount(0);
  await expect(page.getByRole("row", { name: /Old Internship Course/ })).toContainText("Cloud Internship");
  await page.getByRole("combobox", { name: "Filter by course type" }).click();
  await page.getByRole("option", { name: "Regular Course" }).click();
  await expect(page.getByRole("row", { name: /Python Basics/ })).toContainText("₹4999");
  await expect(page.getByRole("row", { name: /Old Internship Course/ })).toHaveCount(0);
});

test("a course already linked cannot be made a regular course from the edit form", async ({ page }) => {
  await page.goto("/courses/c-old");
  await page.getByRole("button", { name: "Edit" }).click();
  await expect(page.getByRole("dialog").getByLabel("Course type", { exact: true })).toBeDisabled();
  await expect(page.getByText("Linked to an internship: unlink it before making it a regular course.")).toBeVisible();
});

test("an internship's LMS course section shows its course, creates a new one here and brings you back", async ({ page }) => {
  await page.goto("/our-internships/int-1?tab=onboarding-settings&section=lms-course");
  await expect(page.getByRole("heading", { name: "LMS course" })).toBeVisible();
  await expect(page.getByRole("combobox", { name: "LMS course" })).toHaveValue("");
  await expect(page.getByRole("combobox", { name: "LMS course" }).locator("option")).toHaveText(["Choose a course...", "Old Internship Course", "Cloud Internship Course (not published)"]);
  await page.getByRole("button", { name: "Create a new internship course" }).click();
  await expect(page).toHaveURL(/\/courses\?new=internship&internship=int-1/);
  await expect(page.getByRole("dialog").getByLabel("Course type", { exact: true })).toHaveValue("internship");
  await expect(page.getByLabel("Internship", { exact: true })).toHaveValue("int-1");
  await fill(page, "DevSecOps Level-1", "devsecops-level-1");
  await page.getByRole("button", { name: "Create course" }).click();
  // back on the same internship, on its LMS course section, showing the new course
  await expect(page).toHaveURL(/\/our-internships\/int-1\?tab=onboarding-settings&section=lms-course/);
  await expect(page.getByTestId("current-course")).toContainText("DevSecOps Level-1");
  await expect(page.getByTestId("current-course")).toContainText("Draft");
  expect(mock.links).toEqual([{ internship: "int-1", course: "c-new-1", confirm: false }]);
});

test("choosing another course for an internship asks first, and the server's refusal is shown plainly", async ({ page }) => {
  await page.goto("/our-internships/int-2?tab=onboarding-settings&section=lms-course");
  await expect(page.getByTestId("current-course")).toContainText("Old Internship Course");
  page.once("dialog", (d) => d.dismiss());
  await page.getByRole("combobox", { name: "LMS course" }).selectOption("c-hidden");
  expect(mock.links).toEqual([]); // declined: nothing was sent
  mock.failNextLink = true;
  page.once("dialog", (d) => d.accept());
  await page.getByRole("combobox", { name: "LMS course" }).selectOption("c-hidden");
  await expect(page.getByRole("alert")).toContainText("students already have LMS access");
  await expect(page.getByTestId("current-course")).toContainText("Old Internship Course"); // unchanged
});
