import type { Page, Route } from "@playwright/test";

const json = (route: Route, body: unknown, status = 200) => route.fulfill({ status, contentType: "application/json", body: JSON.stringify(body) });
const envelope = (code: string, message: string, details: unknown = null) => ({ success: false, error: { code, message, details } });

interface Internship {
  id: string;
  title: string;
  status: "selecting" | "offers_released" | "closed";
  lms_course_id: string | null;
  fee: { currency: string; total: string; base: string; discount: string; tax_mode: string; tax_label: string; tax: string } | null;
}
interface Course {
  id: string;
  title: string;
  slug: string;
  course_type: "regular" | "internship";
  price: number;
  show_internship_fee: boolean;
  is_published: boolean;
  level: string;
  duration_hours: number | null;
  category_id: string | null;
  short_description: string | null;
  description: string | null;
  thumbnail_url: string | null;
}

export interface CoursesMock {
  courses: Course[];
  internships: Internship[];
  /** what the page sent */
  created: Record<string, unknown>[];
  updated: Record<string, unknown>[];
  links: { internship: string; course: string | null; confirm: boolean }[];
  /** make the next link fail like the server would when students are enrolled */
  failNextLink: boolean;
  unhandled: string[];
}

const FEE = { currency: "INR", total: "5900.00", base: "5000.00", discount: "0.00", tax_mode: "exclusive", tax_label: "GST", tax: "900.00" };

export function seed(): Pick<CoursesMock, "courses" | "internships"> {
  const course = (over: Partial<Course>): Course => ({
    id: "c-x", title: "x", slug: "x", course_type: "regular", price: 0, show_internship_fee: false, is_published: true, level: "beginner",
    duration_hours: null, category_id: null, short_description: null, description: null, thumbnail_url: null, ...over,
  });
  return {
    courses: [
      course({ id: "c-py", title: "Python Basics", slug: "python-basics", price: 4999, duration_hours: 20 }),
      course({ id: "c-old", title: "Old Internship Course", slug: "old", course_type: "internship", show_internship_fee: true }),
      course({ id: "c-hidden", title: "Cloud Internship Course", slug: "cloud", course_type: "internship", is_published: false }),
    ],
    internships: [
      { id: "int-1", title: "DevSecOps Internship", status: "selecting", lms_course_id: null, fee: FEE },
      { id: "int-2", title: "Cloud Internship", status: "selecting", lms_course_id: "c-old", fee: FEE },
      { id: "int-3", title: "Finished Internship", status: "closed", lms_course_id: null, fee: null },
    ],
  };
}

/** A small, stateful stand-in for the courses and internships APIs (the page's own code is real; only the server is replaced). */
export async function mockCourses(page: Page): Promise<CoursesMock> {
  const state: CoursesMock = { ...seed(), created: [], updated: [], links: [], failNextLink: false, unhandled: [] };
  await page.addInitScript(() => {
    localStorage.setItem(
      "erpx-auth",
      JSON.stringify({
        state: { accessToken: "t", refreshToken: "r", isAuthenticated: true, user: { id: "u1", email: "admin@example.com", fullName: "Admin", status: "active", isEmailVerified: true, twoFactorEnabled: false } },
        version: 0,
      }),
    );
  });
  const titleOf = (id: string | null) => state.courses.find((c) => c.id === id)?.title ?? null;
  const asAdmin = (c: Course) => ({
    ...c,
    organization_id: "org", created_at: "2026-11-01T00:00:00Z",
    linked_internships: state.internships.filter((i) => i.lms_course_id === c.id).map((i) => ({ id: i.id, title: i.title, status: i.status, fee: c.course_type === "internship" && c.show_internship_fee ? i.fee : null })),
  });
  const internshipOut = (i: Internship) => ({
    id: i.id, title: i.title, description: null, scope: "all", institution_id: null, institution_name: null, event_id: null, event_name: null, status: i.status,
    selected_count: 0, offers_released_at: null, lms_course_id: i.lms_course_id, lms_course_title: titleOf(i.lms_course_id), created_at: "2026-11-01T00:00:00Z",
  });

  await page.route("**/api/v1/**", async (route) => {
    const req = route.request();
    const p = new URL(req.url()).pathname.replace(/^\/api\/v1/, "").replace(/\/$/, "");
    const query = new URL(req.url()).searchParams;
    const m = req.method();
    const body = () => (req.postDataJSON() ?? {}) as Record<string, unknown>;

    if (p === "/authorization/me") return json(route, { user_id: "u1", roles: [], effective_permissions: ["courses.view", "courses.manage", "our_internships.view", "our_internships.manage", "our_internships.finance.view"], is_superuser: false });
    if (/^\/(students|employees|trainers)\/me$/.test(p)) return json(route, envelope("not_found", "not found"), 404);
    if (p === "/notifications/me") return json(route, { items: [], total: 0 });
    if (p === "/notifications/me/unread-count") return json(route, { unread_count: 0 });
    if (p === "/courses/categories") return json(route, []);

    if (p === "/courses" && m === "GET") {
      let items = state.courses;
      if (query.get("course_type")) items = items.filter((c) => c.course_type === query.get("course_type"));
      return json(route, { items: items.map(asAdmin), total: items.length, skip: 0, limit: 20 });
    }
    if (p === "/courses" && m === "POST") {
      const b = body();
      state.created.push(b);
      if (b.course_type === "internship" && b.price) return json(route, envelope("validation_error", "An internship course has no price of its own: its fee comes from the internship's onboarding settings."), 422);
      const c: Course = {
        id: `c-new-${state.created.length}`, title: String(b.title), slug: String(b.slug), course_type: (b.course_type as Course["course_type"]) ?? "regular", price: Number(b.price ?? 0),
        show_internship_fee: !!b.show_internship_fee, is_published: false, level: String(b.level ?? "beginner"), duration_hours: (b.duration_hours as number) ?? null,
        category_id: null, short_description: null, description: null, thumbnail_url: null,
      };
      state.courses.push(c);
      return json(route, asAdmin(c), 201);
    }
    const courseMatch = p.match(/^\/courses\/([^/]+)$/);
    if (courseMatch && m === "GET") {
      const c = state.courses.find((x) => x.id === courseMatch[1]);
      return c ? json(route, asAdmin(c)) : json(route, envelope("not_found", "Course not found"), 404);
    }
    if (courseMatch && m === "PATCH") {
      const c = state.courses.find((x) => x.id === courseMatch[1])!;
      state.updated.push(body());
      Object.assign(c, body());
      return json(route, asAdmin(c));
    }
    if (/^\/courses\/[^/]+\/chapters/.test(p) || /^\/lms\//.test(p)) return json(route, []);

    if (p === "/our-internships" && m === "GET") return json(route, state.internships.map(internshipOut));
    const iMatch = p.match(/^\/our-internships\/([^/]+)$/);
    if (iMatch && m === "GET") {
      const i = state.internships.find((x) => x.id === iMatch[1]);
      return i ? json(route, internshipOut(i)) : json(route, envelope("not_found", "not found"), 404);
    }
    if (iMatch && m === "PATCH") {
      const i = state.internships.find((x) => x.id === iMatch[1])!;
      const b = body();
      const confirm = !!b.confirm_replace;
      state.links.push({ internship: i.id, course: (b.lms_course_id as string | null) ?? null, confirm });
      if (state.failNextLink) {
        state.failNextLink = false;
        return json(route, envelope("conflict", "3 students already have LMS access through \"Old Internship Course\". The course cannot be changed while students are enrolled: revoke their access first, or keep this course.", { code: "course_in_use", enrolled: 3 }), 409);
      }
      if (i.lms_course_id && b.lms_course_id !== i.lms_course_id && !confirm) return json(route, envelope("conflict", `This internship already uses "${titleOf(i.lms_course_id)}". Confirm to replace it.`, { code: "confirm_replace" }), 409);
      i.lms_course_id = (b.lms_course_id as string | null) ?? null;
      return json(route, internshipOut(i));
    }
    const optMatch = p.match(/^\/our-internships\/([^/]+)\/lms\/courses$/);
    if (optMatch) {
      const i = state.internships.find((x) => x.id === optMatch[1])!;
      return json(route, state.courses.filter((c) => c.course_type === "internship" || c.id === i.lms_course_id).map((c) => ({
        id: c.id, title: c.title, is_published: c.is_published, course_type: c.course_type, level: c.level, duration_hours: c.duration_hours, is_current: c.id === i.lms_course_id,
        ready: c.is_published, problem: c.is_published ? null : "Not published yet.", also_used_by: state.internships.filter((o) => o.lms_course_id === c.id && o.id !== i.id).map((o) => o.title),
      })));
    }
    if (/^\/our-internships\/[^/]+\/my-access$/.test(p)) return json(route, { role: "admin", can_delete: true, access_from: null, access_until: null, status: null });
    if (/^\/our-internships\/[^/]+\/onboarding-flow\/config$/.test(p)) return json(route, { can_view_finance: false, can_edit_finance: false, settings: { modes: { mode: "manual" }, deadlines: { timezone: "Asia/Kolkata" } }, version: 1 });
    if (/^\/our-internships\/[^/]+\/performance$/.test(p)) return json(route, { exams: [], hackathons: [], students: [], teams: [], total_students: 0 });
    if (/^\/our-internships\/[^/]+\/(students\/destinations|selected|instructors)$/.test(p)) return json(route, p.endsWith("selected") ? { items: [], total: 0 } : []);

    state.unhandled.push(`${m} ${p}`);
    return json(route, envelope("not_stubbed", "not stubbed"), 404);
  });
  return state;
}
