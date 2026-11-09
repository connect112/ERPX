import { readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import type { Page, Route } from "@playwright/test";

import { asset, view } from "../../src/features/internship-onboarding/components/receipt-fixtures";

const dir = path.dirname(fileURLToPath(import.meta.url));
export const SAMPLE_PDF = readFileSync(path.join(dir, "../fixtures/receipt-sample.pdf"));
export const ISSUED_PDF = readFileSync(path.join(dir, "../fixtures/receipt-issued.pdf"));
/** A real 1x1 PNG, used as the uploaded logo. */
export const PNG = Buffer.from("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==", "base64");

export const INTERNSHIP = "11111111-1111-4111-8111-111111111111";
const json = (route: Route, body: unknown, status = 200) => route.fulfill({ status, contentType: "application/json", body: JSON.stringify(body) });

export interface Mock {
  /** API paths that nothing handled (the test fails if the page needs something this stub does not know). */
  unhandled: string[];
  previews: number;
  uploads: number;
}

/** Signs in with a stored session and answers the API calls the internship page makes; PDFs come from real generated files. */
export async function mockApi(page: Page): Promise<Mock> {
  const mock: Mock = { unhandled: [], previews: 0, uploads: 0 };
  const assets: ReturnType<typeof asset>[] = [];
  await page.addInitScript(() => {
    localStorage.setItem(
      "erpx-auth",
      JSON.stringify({
        state: {
          accessToken: "t",
          refreshToken: "r",
          isAuthenticated: true,
          user: { id: "u1", email: "finance@example.com", fullName: "Finance Manager", status: "active", isEmailVerified: true, twoFactorEnabled: false },
        },
        version: 0,
      }),
    );
  });
  await page.route("**/api/v1/**", async (route) => {
    const req = route.request();
    const url = new URL(req.url());
    const p = url.pathname.replace(/^\/api\/v1/, "");
    const m = req.method();
    if (process.env.MOCK_LOG) console.log("API", m, p);
    if (m === "GET" && p === `/our-internships/${INTERNSHIP}`)
      return json(route, { id: INTERNSHIP, title: "Cyber Security Internship", description: null, scope: "all", institution_id: null, institution_name: null, event_id: null, event_name: null, status: "selecting", selected_count: 1, offers_released_at: null, lms_course_id: null, lms_course_title: null, created_at: "2026-11-01T00:00:00Z" });
    if (p === `/our-internships/${INTERNSHIP}/my-access`) return json(route, { role: "instructor", can_delete: false, access_from: null, access_until: null, status: "active" });
    if (p === `/our-internships/${INTERNSHIP}/onboarding-flow/config`)
      return json(route, { can_view_finance: true, can_edit_finance: true, settings: { modes: { mode: "manual" }, deadlines: { timezone: "Asia/Kolkata" } }, version: 1 });
    if (p === `/our-internships/${INTERNSHIP}/receipt-designer` && m === "GET") return json(route, view({ assets: [...assets] }));
    if (p === `/our-internships/${INTERNSHIP}/receipt-designer/preview`) {
      mock.previews += 1;
      return route.fulfill({ status: 200, contentType: "application/pdf", headers: { "x-page-count": "1", "x-watermark": "SAMPLE - NOT A VALID RECEIPT" }, body: SAMPLE_PDF });
    }
    if (p === `/our-internships/${INTERNSHIP}/receipt-designer/assets` && m === "POST") {
      mock.uploads += 1;
      const a = asset(`asset-${mock.uploads}`, "company-logo.png");
      assets.unshift(a);
      return json(route, a, 201);
    }
    if (/\/receipt-designer\/assets\/[^/]+\/image$/.test(p)) return route.fulfill({ status: 200, contentType: "image/png", body: PNG });
    if (p === `/our-internships/${INTERNSHIP}/receipts` && m === "GET")
      return json(route, {
        total: 1,
        items: [{ id: "d1", number: "RCPT-2026-000001", kind: "receipt", student: "Sample Student", email: "student@example.com", internship: "Cyber Security Internship", application: "ERPX-INT-2026-000001", amount: "5900.00", currency: "INR", paid_on: "2026-11-09", method: "Online (Cashfree)", issued_at: "2026-11-09T05:00:00Z", email_status: "sent", emailed_at: "2026-11-09T05:01:00Z", transaction_id: "tx1", design_source: null, design_version: null, pages: 1, engine: "receipt_pdf" }],
      });
    if (/\/receipts\/d1\/pdf$/.test(p)) return route.fulfill({ status: 200, contentType: "application/pdf", body: ISSUED_PDF });
    if (p === `/our-internships/${INTERNSHIP}/performance`) return json(route, { exams: [], hackathons: [], students: [], teams: [], total_students: 0 });
    if (p === `/our-internships/${INTERNSHIP}/onboarding-flow/dashboard`) return json(route, { rows: [], metrics: {}, money: { payable: "0", received: "0", outstanding: "0" } });
    if (p === "/authorization/me")
      return json(route, { user_id: "u1", roles: [], effective_permissions: ["our_internships.view", "our_internships.finance.view", "our_internships.finance.manage"], is_superuser: false });
    if (/^\/(students|employees|trainers)\/me$/.test(p)) return json(route, { detail: "not found" }, 404); // an account that is none of those
    if (p === "/notifications/me") return json(route, { items: [], total: 0, page: 1, page_size: 20, unread_count: 0 });
    if (p === "/notifications/me/unread-count") return json(route, { count: 0, unread_count: 0 });
    if (m === "GET" && /onboarding-flow\/(payment-accounts|payments|students|templates)|payment-accounts|destinations|instructors|\/selected$/.test(p)) return json(route, []);
    mock.unhandled.push(`${m} ${p}`);
    return json(route, { detail: "not stubbed" }, 404);
  });
  return mock;
}
