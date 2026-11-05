/**
 * Characterization harness for every Zod schema in the web app.
 *
 * It was written BEFORE the Zod 3 -> 4 migration and its golden file (`fixture.json`) was recorded
 * on Zod 3. The same probes run on whatever Zod version is installed, so the test shows exactly
 * where behaviour (accepted input, parsed output, error message, error order) moved.
 *
 * The probes are version independent: they are plain data. Per schema the fixture stores the object
 * keys and one "baseline" value per key; the probes are then derived from that data only, never from
 * Zod internals, so a different Zod version receives exactly the same inputs.
 */

/** Marks "leave this key out of the input" (JSON cannot hold `undefined`). */
export const OMIT = "__omit__";

/** Values tried, one at a time, in every field of every object schema (the rest stay at baseline). */
export const FIELD_PROBES: unknown[] = [
  OMIT,
  "",
  " ",
  "  padded  ",
  "x",
  "ab",
  "-1",
  "0",
  "0.5",
  "1",
  "1.5",
  "1e3",
  "12abc",
  "NaN",
  "Infinity",
  "2025-02-30",
  "not-an-email",
  "https://",
  "x".repeat(300),
  null,
  true,
  false,
  0,
  5,
  -5,
  1.5,
  [],
  {},
];

/** Whole-object probes (every key gets the same value). */
export const OBJECT_PROBES: unknown[] = ["", "x", "1", "-1", "0", null];

/** Candidates tried (in order) against a single field to find a value it accepts. */
const BASELINE_CANDIDATES: unknown[] = [
  "Sample text",
  "sample@example.com",
  "https://example.com",
  "2025-06-15",
  "2025-06-15T10:00",
  "10:30",
  "+919876543210",
  "9876543210",
  "Passw0rd!xyz",
  "5",
  5,
  "100",
  true,
  ["a"],
  [{}],
  [],
  {},
];

/** Hand-written baselines for fields no generic candidate satisfies. Keyed `schemaName.field`. */
export const BASELINE_OVERRIDES: Record<string, unknown> = {
  // The entity type must be lower_snake_case.
  "workflow/schemas/workflow-schemas.ts#workflowFormSchema.entityType": "leave_request",
  // Cross-field rule: the two passwords must be equal.
  "auth/schemas/auth-schemas.ts#registerSchema.password": "Passw0rd!xyz",
  "auth/schemas/auth-schemas.ts#registerSchema.confirmPassword": "Passw0rd!xyz",
  "auth/schemas/auth-schemas.ts#resetPasswordSchema.password": "Passw0rd!xyz",
  "auth/schemas/auth-schemas.ts#resetPasswordSchema.confirmPassword": "Passw0rd!xyz",
  "auth/schemas/auth-schemas.ts#changePasswordSchema.newPassword": "Passw0rd!xyz",
  "auth/schemas/auth-schemas.ts#changePasswordSchema.confirmPassword": "Passw0rd!xyz",
};

// eslint-disable-next-line @typescript-eslint/no-explicit-any
type AnySchema = any;

export function isSchema(v: unknown): v is AnySchema {
  return !!v && typeof (v as AnySchema).safeParse === "function" && typeof (v as AnySchema).parse === "function";
}

/** The field map of an object schema, looking through refine()/transform() wrappers. Works on Zod 3 and 4. */
export function shapeOf(schema: AnySchema): Record<string, AnySchema> | null {
  let cur = schema;
  for (let i = 0; i < 6 && cur; i++) {
    const def = cur._def ?? cur.def;
    const direct = cur.shape ?? (typeof def?.shape === "function" ? def.shape() : def?.shape);
    if (direct && typeof direct === "object") return direct as Record<string, AnySchema>;
    cur = def?.schema ?? def?.innerType ?? def?.in;
  }
  return null;
}

function enumOptions(field: AnySchema): unknown[] {
  let cur = field;
  for (let i = 0; i < 6 && cur; i++) {
    const def = cur._def ?? cur.def;
    if (Array.isArray(cur.options)) return cur.options as unknown[];
    if (Array.isArray(def?.values)) return def.values as unknown[];
    cur = def?.innerType ?? def?.schema ?? def?.in;
  }
  return [];
}

function sortKeys(v: unknown): unknown {
  if (Array.isArray(v)) return v.map(sortKeys);
  if (v && typeof v === "object" && !(v instanceof Date)) {
    return Object.fromEntries(
      Object.keys(v as object)
        .sort()
        .map((k) => [k, sortKeys((v as Record<string, unknown>)[k])]),
    );
  }
  return v;
}

function encodeData(v: unknown): unknown {
  if (v === undefined) return "<undefined>";
  if (typeof v === "number" && Number.isNaN(v)) return "<NaN>";
  if (v === Infinity) return "<Infinity>";
  if (v === -Infinity) return "<-Infinity>";
  if (typeof v === "bigint") return `<bigint ${v}>`;
  if (v instanceof Date) return `<date ${Number.isNaN(v.getTime()) ? "invalid" : v.toISOString()}>`;
  if (Array.isArray(v)) return v.map(encodeData);
  if (v && typeof v === "object") return Object.fromEntries(Object.entries(v).map(([k, x]) => [k, encodeData(x)]));
  return v;
}

/**
 * Only what the schema CHANGED is recorded for an accepted input (coerced, trimmed, defaulted, dropped
 * keys), not the whole object: that keeps the fixture small and the differences readable.
 */
function changes(input: unknown, output: unknown): unknown {
  if (!input || typeof input !== "object" || Array.isArray(input) || !output || typeof output !== "object" || Array.isArray(output)) return output;
  const delta: Record<string, unknown> = {};
  const inObj = input as Record<string, unknown>;
  const outObj = output as Record<string, unknown>;
  for (const k of Object.keys(outObj)) {
    if (JSON.stringify(encodeData(inObj[k])) !== JSON.stringify(encodeData(outObj[k]))) delta[k] = outObj[k];
  }
  for (const k of Object.keys(inObj)) if (!(k in outObj)) delta[`-${k}`] = true;
  return delta;
}

/** One compact line-based string per outcome: `ok <json of changes>` or `err` followed by `path | message` lines. */
export function outcomeOf(schema: AnySchema, input: unknown): string {
  const r = schema.safeParse(input);
  if (r.success) return `ok ${JSON.stringify(sortKeys(encodeData(changes(input, r.data))))}`;
  const issues: { path: unknown[]; message: string }[] = r.error.issues;
  return ["err", ...issues.map((i) => `${i.path.join(".") || "<root>"} | ${i.message}`)].join("\n");
}

function clone<T>(v: T): T {
  return v === undefined ? v : (JSON.parse(JSON.stringify(v)) as T);
}

/** `a.b.c` style deep assignment on a clone; `OMIT` deletes the key. */
function withValue(base: Record<string, unknown>, path: string, value: unknown): Record<string, unknown> {
  const out = clone(base);
  const parts = path.split(".");
  let cur: Record<string, unknown> = out;
  for (let i = 0; i < parts.length - 1; i++) cur = cur[parts[i]] as Record<string, unknown>;
  const last = parts[parts.length - 1];
  if (value === OMIT) delete cur[last];
  else cur[last] = value;
  return out;
}

function buildInput(baseline: Record<string, unknown>, path: string | null, value: unknown): Record<string, unknown> {
  const out = path === null ? clone(baseline) : withValue(baseline, path, value);
  for (const k of Object.keys(out)) if (out[k] === OMIT) delete out[k];
  return out;
}

/** Element schema of an array field (Zod 3 and 4), looking through optional()/default() wrappers. */
function elementOf(field: AnySchema): AnySchema | null {
  let cur = field;
  for (let i = 0; i < 6 && cur; i++) {
    const def = cur._def ?? cur.def;
    if (cur.element) return cur.element;
    if (def?.type && typeof def.type === "object" && typeof def.type.safeParse === "function") return def.type;
    cur = def?.innerType ?? def?.schema ?? def?.in;
  }
  return null;
}

/** An accepted value for one field: a generic candidate, or (for arrays of objects) two derived elements. */
function deriveValue(field: AnySchema, name: string, overrides: Record<string, unknown>, depth = 0): unknown {
  if (name in overrides) return overrides[name];
  const candidates = [...enumOptions(field).slice(0, 1), ...BASELINE_CANDIDATES];
  const hit = candidates.find((c) => field.safeParse(c).success);
  if (hit !== undefined) return hit;
  const el = depth < 2 ? elementOf(field) : null;
  const elShape = el ? shapeOf(el) : null;
  if (elShape) {
    const one = Object.fromEntries(Object.keys(elShape).map((k) => [k, deriveValue(elShape[k], `${name}[].${k}`, overrides, depth + 1)]));
    const arr = [clone(one), clone(one)];
    if (field.safeParse(arr).success) return arr;
  }
  return OMIT;
}

/** All probe paths: each top-level key, plus each key of the first element of an array of objects. */
function probePaths(shape: Record<string, AnySchema>, baseline: Record<string, unknown>): string[] {
  const paths: string[] = [];
  for (const k of Object.keys(shape)) {
    paths.push(k);
    const v = baseline[k];
    if (Array.isArray(v) && v.length && v[0] && typeof v[0] === "object") {
      for (const ek of Object.keys(v[0] as object)) paths.push(`${k}.0.${ek}`);
    }
  }
  return paths;
}

export interface SchemaRecord {
  /** Probe paths (`field`, or `lines.0.description` for the first element of an array of objects). */
  keys: string[];
  /** One accepted value per top-level key (OMIT when nothing generic was accepted). */
  baseline: Record<string, unknown>;
  /** Did the baseline object as a whole parse? (False when a cross-field rule needs hand-tuning.) */
  baselineAccepted: boolean;
  /** `[outcome of the baseline, outcome of an empty object, ...object probes]` as indexes into `outcomes`. */
  whole: number[];
  /** probe path -> outcome index for every entry of FIELD_PROBES. */
  fields: Record<string, number[]>;
}

export interface Fixture {
  recordedWith: string;
  fieldProbeCount: number;
  objectProbeCount: number;
  outcomes: string[];
  schemas: Record<string, SchemaRecord>;
}

function wholeInputs(baseline: Record<string, unknown>): Record<string, unknown>[] {
  const topKeys = Object.keys(baseline);
  return [buildInput(baseline, null, null), {}, ...OBJECT_PROBES.map((p) => Object.fromEntries(topKeys.map((k) => [k, p])))];
}

/** Records the current behaviour of a schema. The outcome table is shared (deduplicated) across schemas. */
export function record(name: string, schema: AnySchema, table: Map<string, number>, overrides = BASELINE_OVERRIDES): SchemaRecord | null {
  const shape = shapeOf(schema);
  if (!shape) return null;
  const idx = (s: string) => {
    let i = table.get(s);
    if (i === undefined) {
      i = table.size;
      table.set(s, i);
    }
    return i;
  };
  const scoped = Object.fromEntries(Object.entries(overrides).filter(([k]) => k.startsWith(`${name}.`)).map(([k, v]) => [k.slice(name.length + 1), v]));

  const baseline: Record<string, unknown> = {};
  for (const k of Object.keys(shape)) baseline[k] = deriveValue(shape[k], k, scoped);
  const baselineAccepted = schema.safeParse(buildInput(baseline, null, null)).success;
  const keys = probePaths(shape, baseline);

  const whole = wholeInputs(baseline).map((i) => idx(outcomeOf(schema, i)));
  const fields: Record<string, number[]> = {};
  for (const k of keys) fields[k] = FIELD_PROBES.map((p) => idx(outcomeOf(schema, buildInput(baseline, k, p))));
  return { keys, baseline, baselineAccepted, whole, fields };
}

/** Re-runs the recorded probes against the current Zod and returns the outcome of each, in fixture order. */
export function replay(schema: AnySchema, rec: SchemaRecord): { whole: string[]; fields: Record<string, string[]> } {
  return {
    whole: wholeInputs(rec.baseline).map((i) => outcomeOf(schema, i)),
    fields: Object.fromEntries(rec.keys.map((k) => [k, FIELD_PROBES.map((p) => outcomeOf(schema, buildInput(rec.baseline, k, p)))])),
  };
}

export function describeProbe(p: unknown): string {
  return p === OMIT ? "<omitted>" : JSON.stringify(p)?.slice(0, 40) ?? String(p);
}
