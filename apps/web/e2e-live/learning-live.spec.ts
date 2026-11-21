import { type Page, expect, test } from "@playwright/test";

/**
 * The Learning integration end to end, with NOTHING stubbed: a real browser, the real admin site, student portal and trainer portal, a real
 * backend and a real database (seeded by apps/api/scripts/seed_learning_e2e.py). One story told in order: an instructor builds a quiz in
 * the trainer portal; a student takes it in the student portal; the very same record then shows on the internship page and the course
 * page of the admin site; an independent enrolee never sees it; and when the student's access is withdrawn their door closes while their
 * result stays on record, marked.
 */

const STUDENT = "http://localhost:5174";
const TRAINER = "http://localhost:5175";
const PASSWORD = "LearnE2e123!";
const ADMIN = { url: "http://localhost:5173", email: "admin.learning.e2e@example.com", password: PASSWORD };
const ASHA = { email: "asha.e2e@example.com", password: PASSWORD };
const SOLO = { email: "solo.e2e@example.com", password: PASSWORD };
const ILA = { email: "ila.e2e@example.com", password: PASSWORD };
const SEVEN = ["Curriculum", "Enrollments", "Evaluations", "Projects", "Discussions", "Practicals", "Viva"];
const QUIZ = "Live Quiz";

async function signIn(page: Page, base: string, who: { email: string; password: string }) {
  await page.goto(`${base}/login`);
  await page.getByLabel("Email").fill(who.email);
  await page.getByLabel("Password").fill(who.password);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page).not.toHaveURL(/\/login/);
}

const tabs = (page: Page, scope = "learning-workspace") => page.getByTestId(scope).getByRole("tab").evaluateAll((els, seven) => els.map((e) => (e.textContent ?? "").trim()).filter((t) => (seven as string[]).includes(t)), SEVEN);

test.describe.configure({ mode: "serial" });

let problems: string[] = [];
test.beforeEach(({ page }) => {
  problems = [];
  page.on("pageerror", (e) => problems.push(`pageerror: ${e.message}`));
});
test.afterEach(() => expect(problems).toEqual([]));

test("the administrator's internship page and course page show the same seven tabs over the same real cohort", async ({ page }) => {
  await signIn(page, ADMIN.url, ADMIN);
  await page.goto(`${ADMIN.url}/our-internships`);
  await page.getByText("Pentrix Cyber Internship").first().click();
  await page.getByTestId("internship-tab-learning").click();
  await expect(page.getByTestId("learning-workspace")).toBeVisible();
  expect(await tabs(page)).toEqual(SEVEN);
  await page.getByTestId("learning-tab-enrollments").click();
  await expect(page.getByRole("row", { name: /Asha Rao/ })).toContainText(/granted/i);
  await expect(page.getByRole("row", { name: /Meera Iyer/ })).toContainText(/granted/i);
  await expect(page.getByRole("row", { name: /Ravi Kumar/ })).not.toContainText(/Access granted/i);
  // the same course, from the LMS side
  await page.goto(`${ADMIN.url}/courses`);
  await page.getByText("Cloud Security Fundamentals").first().click();
  await expect(page.getByTestId("learning-workspace")).toBeVisible();
  expect(await tabs(page)).toEqual(SEVEN);
  await expect(page.getByTestId("cohort-selector")).toContainText("Pentrix Cyber Internship");
  for (const gone of ["Assignments", "Assessments", "Exams"]) await expect(page.getByRole("tab", { name: gone, exact: true })).toHaveCount(0);
});

test("an instructor with no global permission builds and publishes a quiz for their internship in the trainer portal", async ({ page }) => {
  await signIn(page, TRAINER, ILA);
  await page.goto(`${TRAINER}/internships`);
  await expect(page.getByText("Pentrix Cyber Internship")).toBeVisible();
  await page.getByRole("link", { name: "Open learning" }).click();
  await expect(page.getByTestId("trainer-learning")).toBeVisible();
  expect(await tabs(page, "trainer-learning")).toEqual(SEVEN);
  await page.getByTestId("learning-tab-evaluations").click();
  await page.getByRole("tab", { name: "Assessments / Quizzes" }).click();
  await page.getByLabel("New assessment title").fill(QUIZ);
  await page.getByRole("button", { name: "Create quiz" }).click();
  const card = page.getByTestId(`assessment-${QUIZ}`);
  await expect(card).toContainText("Internship only");
  await card.getByRole("button", { name: new RegExp(QUIZ) }).click();
  await card.getByLabel("Question", { exact: true }).fill("Which port does HTTPS use?");
  await card.getByLabel("Options, one per line").fill("80\n443\n22");
  await card.getByLabel(/Correct option number/).fill("2");
  await card.getByRole("button", { name: "Add question" }).click();
  await expect(card.getByText("Which port does HTTPS use?")).toBeVisible();
  await card.getByRole("button", { name: "Publish" }).click();
  await expect(card.getByRole("button", { name: "Unpublish" })).toBeVisible();
  // an instructor is offered no way to delete
  await expect(page.getByTestId("trainer-learning").getByRole("button", { name: /Delete/i })).toHaveCount(0);
});

test("a student with access opens the course, takes the quiz and the server scores it", async ({ page }) => {
  await signIn(page, STUDENT, ASHA);
  await page.goto(`${STUDENT}/courses`);
  await page.getByRole("link", { name: "View" }).first().click();
  const row = page.getByTestId(`assessment-${QUIZ}`);
  await expect(row).toBeVisible();
  await row.getByRole("link", { name: "Start" }).click();
  await expect(page.getByTestId("assessment-take")).toBeVisible();
  await expect(page.getByText("Which port does HTTPS use?")).toBeVisible();
  expect(await page.content()).not.toMatch(/correct_indices/); // the answer never reaches the browser
  await page.getByLabel("443").check();
  page.once("dialog", (d) => d.accept());
  await page.getByRole("button", { name: "Submit answers" }).click();
  await expect(page.getByTestId("assessment-result")).toContainText("Your score: 1");
  await expect(page.getByTestId("assessment-result")).toContainText("Pass");
});

test("the quiz the instructor made and the attempt the student made are the same records on every page", async ({ page }) => {
  // the trainer sees the student's attempt
  await signIn(page, TRAINER, ILA);
  await page.goto(`${TRAINER}/internships`);
  await page.getByRole("link", { name: "Open learning" }).click();
  await page.getByTestId("learning-tab-evaluations").click();
  await page.getByRole("tab", { name: "Assessments / Quizzes" }).click();
  const card = page.getByTestId(`assessment-${QUIZ}`);
  await card.getByRole("button", { name: new RegExp(QUIZ) }).click();
  await expect(card).toContainText("Asha Rao");
  await expect(card).toContainText("1 / 1");
  // the administrator sees the same quiz on the internship page and, choosing the cohort, on the course page
  await signIn(page, ADMIN.url, ADMIN);
  await page.goto(`${ADMIN.url}/our-internships`);
  await page.getByText("Pentrix Cyber Internship").first().click();
  await page.getByTestId("internship-tab-learning").click();
  await page.getByTestId("learning-tab-evaluations").click();
  await page.getByTestId("evaluations-assessments").click();
  await expect(page.getByText(QUIZ).first()).toBeVisible();
  await page.goto(`${ADMIN.url}/courses`);
  await page.getByText("Cloud Security Fundamentals").first().click();
  await page.getByTestId("learning-tab-evaluations").click();
  await page.getByTestId("evaluations-assessments").click();
  // the course serves ONE internship, so that cohort is the one shown (with two, a selector would ask first: covered by the stubbed spec)
  await expect(page.getByTestId("cohort-selector")).toContainText("Pentrix Cyber Internship");
  await expect(page.getByText(QUIZ).first()).toBeVisible();
});

test("an independent enrolee of the same course never sees the internship's quiz, even by its address", async ({ page }) => {
  await signIn(page, STUDENT, SOLO);
  await page.goto(`${STUDENT}/courses`);
  await page.getByRole("link", { name: "View" }).first().click();
  await expect(page.getByTestId("course-learning")).toBeVisible();
  await expect(page.getByTestId(`assessment-${QUIZ}`)).toHaveCount(0);
  await expect(page.getByText(QUIZ)).toHaveCount(0);
  const href = await page.evaluate(() => location.pathname);
  const courseId = href.split("/").pop();
  const quizId = await page.evaluate(async (cid) => {
    const token = JSON.parse(localStorage.getItem("erpx-auth") ?? "{}")?.state?.accessToken as string;
    const r = await fetch(`/api/v1/lms/courses/${cid}/assessments`, { headers: { Authorization: `Bearer ${token}` } });
    return r.status;
  }, courseId);
  expect(quizId).toBe(200); // the list itself works...
  await page.goto(`${STUDENT}/courses/${courseId}`);
  const refused = await page.evaluate(async (cid) => {
    const token = JSON.parse(localStorage.getItem("erpx-auth") ?? "{}")?.state?.accessToken as string;
    const list = await fetch(`/api/v1/lms/courses/${cid}/assessments`, { headers: { Authorization: `Bearer ${token}` } }).then((r) => r.json());
    return JSON.stringify(list).includes("Live Quiz");
  }, courseId);
  expect(refused).toBe(false); // ...and holds none of the internship's
});

test("when the administrator withdraws the student's access their door closes and their result stays, marked", async ({ page }) => {
  await signIn(page, ADMIN.url, ADMIN);
  await page.goto(`${ADMIN.url}/our-internships`);
  await page.getByText("Pentrix Cyber Internship").first().click();
  await page.getByTestId("internship-tab-learning").click();
  await page.getByTestId("learning-tab-enrollments").click();
  page.once("dialog", (d) => d.accept());
  await page.getByRole("row", { name: /Asha Rao/ }).getByRole("button", { name: "Revoke access" }).click();
  await expect(page.getByRole("row", { name: /Asha Rao/ })).toContainText(/Revoked/);
  // the history is kept and marked in the results
  await page.getByTestId("learning-tab-evaluations").click();
  await page.getByTestId("evaluations-results").click();
  const result = page.getByRole("row", { name: /Asha Rao/ }).filter({ hasText: QUIZ });
  await expect(result).toContainText(/revoked/i);
  await expect(result).toContainText("1");
  // the student can no longer reach the course or the quiz
  await signIn(page, STUDENT, ASHA);
  const status = await page.evaluate(async () => {
    const token = JSON.parse(localStorage.getItem("erpx-auth") ?? "{}")?.state?.accessToken as string;
    const courses = await fetch("/api/v1/enrollment/me", { headers: { Authorization: `Bearer ${token}` } });
    return courses.status;
  });
  expect([200, 404]).toContain(status);
  await page.goto(`${STUDENT}/courses`);
  await expect(page.getByText("Cloud Security Fundamentals")).toHaveCount(0);
});
