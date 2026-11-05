import { isSchema } from "./harness";
import { organizationFormSchema } from "@/features/organizations/schemas/organization-schemas";

// Every module under src/features/**/schemas (tests excluded), loaded eagerly so a NEW schema file
// is picked up automatically and fails the "fixture is complete" check until it is recorded.
const modules = import.meta.glob(["/src/features/**/schemas/*.ts", "!/src/features/**/schemas/*.test.ts"], { eager: true }) as Record<
  string,
  Record<string, unknown>
>;

// Schemas that are built by a function rather than exported as a constant.
const factories: Record<string, unknown> = {
  "organization-schemas.ts#organizationFormSchema(create)": organizationFormSchema("create"),
  "organization-schemas.ts#organizationFormSchema(edit)": organizationFormSchema("edit"),
};

/** `file#exportName` -> schema, sorted by name so the fixture is stable. */
export function allSchemas(): Record<string, unknown> {
  const found: Record<string, unknown> = {};
  for (const [path, mod] of Object.entries(modules)) {
    for (const [exportName, value] of Object.entries(mod)) {
      if (isSchema(value)) found[`${path.replace("/src/features/", "")}#${exportName}`] = value;
    }
  }
  Object.assign(found, Object.fromEntries(Object.entries(factories).map(([k, v]) => [`organizations/schemas/${k}`, v])));
  return Object.fromEntries(Object.entries(found).sort(([a], [b]) => a.localeCompare(b)));
}
