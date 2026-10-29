import { describe, expect, it } from "vitest";

import type { FileFilters, FileItem } from "@/features/storage-manager/api/storage-api";
import { hasActiveFilters, isDeletable, isDeleteReady, nextSort, purgeConfirmText, totalBytes } from "@/features/storage-manager/lib/rules";

function item(overrides: Partial<FileItem> = {}): FileItem {
  return {
    id: "o:x", source: "orphans", source_label: "Unreferenced files", module: "storage", backend: "object_storage",
    name: "a.txt", path: [], size_bytes: 10, content_type: "text/plain", type_group: "text", created_at: null,
    owner: null, organization_id: null, organization_name: null, location: "", status: "orphan", protected: false,
    protected_reason: null, fingerprint: null, is_large: false, previewable: "text", ...overrides,
  };
}

const filters: FileFilters = { path: [], sort: "name", order: "asc", page: 1, page_size: 50 };

describe("isDeletable", () => {
  it("allows an unused, unprotected storage file for a superuser", () => {
    expect(isDeletable(item(), true)).toBe(true);
  });

  it("never offers deletion to anyone but a superuser", () => {
    expect(isDeletable(item(), false)).toBe(false);
  });

  it.each(["in_use", "pending", "missing_object", "protected"] as const)("refuses a %s file", (status) => {
    expect(isDeletable(item({ status }), true)).toBe(false);
  });

  it("refuses protected files and files kept inside the database, whatever their status", () => {
    expect(isDeletable(item({ protected: true }), true)).toBe(false);
    expect(isDeletable(item({ backend: "database" }), true)).toBe(false);
  });
});

describe("isDeleteReady", () => {
  const ready = { blockedCount: 0, reason: "old export nobody uses", typed: "DELETE 2", confirmText: "DELETE 2" };

  it("is ready only when everything is in order", () => {
    expect(isDeleteReady(ready)).toBe(true);
  });

  it("needs the exact confirmation text, including case", () => {
    expect(isDeleteReady({ ...ready, typed: "delete 2" })).toBe(false);
    expect(isDeleteReady({ ...ready, typed: "DELETE 1" })).toBe(false);
    expect(isDeleteReady({ ...ready, typed: "" })).toBe(false);
  });

  it("ignores stray spaces around the confirmation, not inside it", () => {
    expect(isDeleteReady({ ...ready, typed: "  DELETE 2 " })).toBe(true);
    expect(isDeleteReady({ ...ready, typed: "DELETE  2" })).toBe(false);
  });

  it("needs a real reason", () => {
    expect(isDeleteReady({ ...ready, reason: "" })).toBe(false);
    expect(isDeleteReady({ ...ready, reason: "  ok" })).toBe(false); // shorter than 3 once trimmed
  });

  it("is blocked while any selected file is not eligible", () => {
    expect(isDeleteReady({ ...ready, blockedCount: 1 })).toBe(false);
  });
});

describe("purgeConfirmText", () => {
  it("names the number of items", () => {
    expect(purgeConfirmText(3)).toBe("PURGE 3");
  });
});

describe("nextSort", () => {
  it("starts ascending on a new column and flips on the same one", () => {
    expect(nextSort({ sort: "name", order: "asc" }, "size")).toEqual({ sort: "size", order: "asc" });
    expect(nextSort({ sort: "size", order: "asc" }, "size")).toEqual({ sort: "size", order: "desc" });
    expect(nextSort({ sort: "size", order: "desc" }, "size")).toEqual({ sort: "size", order: "asc" });
  });
});

describe("hasActiveFilters", () => {
  it("is false for the default view and true once anything narrows it", () => {
    expect(hasActiveFilters(filters)).toBe(false);
    expect(hasActiveFilters({ ...filters, q: "report" })).toBe(true);
    expect(hasActiveFilters({ ...filters, status: "orphan" })).toBe(true);
    expect(hasActiveFilters({ ...filters, large: true })).toBe(true);
  });
});

describe("totalBytes", () => {
  it("adds up sizes", () => {
    expect(totalBytes([item({ size_bytes: 5 }), item({ size_bytes: 7 })])).toBe(12);
    expect(totalBytes([])).toBe(0);
  });
});
