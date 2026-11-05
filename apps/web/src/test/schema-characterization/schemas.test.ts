import fs from "node:fs";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";
import { FIELD_PROBES, OBJECT_PROBES, describeProbe, outcomeOf, record, replay, type Fixture } from "./harness";
import { allSchemas } from "./schemas";

const FIXTURE = fileURLToPath(new URL("./fixture.json", import.meta.url));
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
            if (got !== want) diffs.push(`whole-object probe #${i}\n  recorded: ${want}\n  now:      ${got}`);
          });
          for (const k of rec.keys) {
            now.fields[k].forEach((got, i) => {
              const want = fixture.outcomes[rec.fields[k][i]];
              if (got !== want) diffs.push(`${k} <- ${describeProbe(FIELD_PROBES[i])}\n  recorded: ${want}\n  now:      ${got}`);
            });
          }
        } else {
          fixture.plain[name].forEach((idx, i) => {
            const got = outcomeOf(schema, FIELD_PROBES[i]);
            const want = fixture.outcomes[idx];
            if (got !== want) diffs.push(`value ${describeProbe(FIELD_PROBES[i])}\n  recorded: ${want}\n  now:      ${got}`);
          });
        }
        expect(diffs).toEqual([]);
      });
    }
  });
}
