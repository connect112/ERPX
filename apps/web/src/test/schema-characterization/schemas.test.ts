import fs from "node:fs";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";
import { installZodMessages } from "@/lib/zod-messages";
import { FIELD_PROBES, OBJECT_PROBES, describeProbe, outcomeOf, record, replay, type Fixture } from "./harness";
import { allSchemas } from "./schemas";

const FIXTURE = fileURLToPath(new URL("./fixture.json", import.meta.url));
// The app installs this once at start-up (main.tsx); the schemas are only equivalent to Zod 3 with it.
installZodMessages();
const schemas = allSchemas();

// `UPDATE_SCHEMA_FIXTURE=1 npx vitest run src/test/schema-characterization` re-records the golden file.
// Only do that on purpose: the fixture is the proof that a dependency upgrade changed nothing.
if (process.env.UPDATE_SCHEMA_FIXTURE) {
  it("records the fixture", () => {
    const zodVersion = (JSON.parse(fs.readFileSync("node_modules/zod/package.json", "utf8")) as { version: string }).version;
    const table = new Map<string, number>();
    const out: Fixture = { recordedWith: `zod ${zodVersion}`, fieldProbeCount: FIELD_PROBES.length, objectProbeCount: OBJECT_PROBES.length, outcomes: [], schemas: {} };
    const plain: Record<string, number[]> = {};
    for (const [name, schema] of Object.entries(schemas)) {
      const rec = record(name, schema, table);
      if (rec) out.schemas[name] = rec;
      else {
        plain[name] = FIELD_PROBES.map((p) => {
          const s = outcomeOf(schema, p);
          if (!table.has(s)) table.set(s, table.size);
          return table.get(s)!;
        });
      }
    }
    out.outcomes = [...table.keys()];
    (out as Fixture & { plain: Record<string, number[]> }).plain = plain;
    fs.writeFileSync(FIXTURE, JSON.stringify(out));
    expect(Object.keys(out.schemas).length).toBeGreaterThan(0);
  });
} else {
  const fixture = JSON.parse(fs.readFileSync(FIXTURE, "utf8")) as Fixture & { plain: Record<string, number[]> };
  const names = [...Object.keys(fixture.schemas), ...Object.keys(fixture.plain)].sort((a, b) => a.localeCompare(b));

  /**
   * Zod 4 differs from Zod 3 in exactly two ways that were reviewed and accepted (everything else, i.e.
   * what is accepted, what is parsed and every error message and its order, must match the recording):
   *
   * 1. After a TYPE error Zod 4 still runs size checks, so a field given the wrong kind of value can
   *    report a second issue at the same path (e.g. an array into `z.string().min(1, "...")`). Forms
   *    only ever show one message per field (the first), so issues after the first at a path are dropped
   *    from both sides before comparing. No form submits a wrong-typed value anyway.
   * 2. The text "Infinity" is no longer a valid number: `z.coerce.number()` turned it into Infinity, which
   *    Zod 3 accepted and JSON cannot carry. It is now rejected with "Number must be finite".
   */
  const firstPerPath = (outcome: string): string => {
    if (!outcome.startsWith("err")) return outcome;
    const seen = new Set<string>();
    const kept = outcome
      .split("\n")
      .slice(1)
      .filter((line) => {
        const path = line.split(" | ")[0];
        if (seen.has(path)) return false;
        seen.add(path);
        return true;
      });
    return ["err", ...kept].join("\n");
  };
  const sameOutcome = (recorded: string, now: string, probe: unknown): boolean => {
    if (probe === "Infinity" && recorded !== now && now.startsWith("err") && now.includes("Number must be finite")) return true;
    return firstPerPath(recorded) === firstPerPath(now);
  };

  describe("schema characterization (recorded on Zod 3)", () => {
    it("covers exactly the schemas that exist (new schema files must be recorded)", () => {
      expect(Object.keys(schemas)).toEqual(names);
    });

    it("uses the same probe lists as the recording", () => {
      expect(FIELD_PROBES).toHaveLength(fixture.fieldProbeCount);
      expect(OBJECT_PROBES).toHaveLength(fixture.objectProbeCount);
    });

    for (const name of names) {
      it(name, () => {
        const schema = schemas[name];
        const diffs: string[] = [];
        const rec = fixture.schemas[name];
        if (rec) {
          const now = replay(schema, rec);
          now.whole.forEach((got, i) => {
            const want = fixture.outcomes[rec.whole[i]];
            if (!sameOutcome(want, got, null)) diffs.push(`whole-object probe #${i}\n  recorded: ${want}\n  now:      ${got}`);
          });
          for (const k of rec.keys) {
            now.fields[k].forEach((got, i) => {
              const want = fixture.outcomes[rec.fields[k][i]];
              if (!sameOutcome(want, got, FIELD_PROBES[i])) diffs.push(`${k} <- ${describeProbe(FIELD_PROBES[i])}\n  recorded: ${want}\n  now:      ${got}`);
            });
          }
        } else {
          fixture.plain[name].forEach((idx, i) => {
            const got = outcomeOf(schema, FIELD_PROBES[i]);
            const want = fixture.outcomes[idx];
            if (!sameOutcome(want, got, FIELD_PROBES[i])) diffs.push(`value ${describeProbe(FIELD_PROBES[i])}\n  recorded: ${want}\n  now:      ${got}`);
          });
        }
        expect(diffs).toEqual([]);
      });
    }
  });
}
