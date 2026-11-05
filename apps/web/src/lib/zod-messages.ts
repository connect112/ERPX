import { z } from "zod";

/**
 * Keeps the wording of Zod's DEFAULT validation messages exactly as it was on Zod 3.
 *
 * Zod 4 rewrote them ("Required" became "Invalid input: expected string, received undefined",
 * "Invalid email" became "Invalid email address", ...). Messages written in the schemas themselves
 * (`.min(1, "Name is required.")`) are untouched by Zod and always win; this only restores the
 * wording of the cases a schema leaves to Zod. Anything not covered here falls through to Zod 4's own
 * message.
 *
 * Installed once at start-up (see main.tsx) and by the schema tests.
 */

function receivedType(value: unknown): string {
  switch (typeof value) {
    case "undefined":
      return "undefined";
    case "string":
      return "string";
    case "number":
      return Number.isNaN(value) ? "nan" : "number";
    case "boolean":
      return "boolean";
    case "function":
      return "function";
    case "bigint":
      return "bigint";
    case "symbol":
      return "symbol";
    default:
      if (Array.isArray(value)) return "array";
      if (value === null) return "null";
      if (value instanceof Map) return "map";
      if (value instanceof Set) return "set";
      if (value instanceof Date) return "date";
      return "object";
  }
}

const joinValues = (values: readonly unknown[], separator = " | ") => values.map((v) => (typeof v === "string" ? `'${v}'` : String(v))).join(separator);

// The raw issue Zod hands to `customError`; typed loosely on purpose (its shape differs per issue code).
type RawIssue = {
  code: string;
  input?: unknown;
  expected?: string;
  origin?: string;
  minimum?: number | bigint;
  maximum?: number | bigint;
  inclusive?: boolean;
  exact?: boolean;
  format?: string;
  prefix?: string;
  suffix?: string;
  includes?: string;
  values?: unknown[];
  divisor?: number;
  keys?: string[];
  inst?: { _zod?: { def?: { type?: string } } };
};

export function zodDefaultMessage(issue: RawIssue): string | undefined {
  switch (issue.code) {
    case "invalid_type": {
      if (issue.input === undefined) return "Required";
      if (issue.expected === "int") return `Expected integer, received ${typeof issue.input === "number" && Number.isFinite(issue.input) ? "float" : receivedType(issue.input)}`;
      if (issue.expected === "number" && (issue.input === Infinity || issue.input === -Infinity)) return "Number must be finite";
      return `Expected ${issue.expected}, received ${receivedType(issue.input)}`;
    }
    case "too_small": {
      const { origin, minimum, inclusive, exact } = issue;
      if (origin === "array") return `Array must contain ${exact ? "exactly" : inclusive ? "at least" : "more than"} ${minimum} element(s)`;
      if (origin === "string") return `String must contain ${exact ? "exactly" : inclusive ? "at least" : "over"} ${minimum} character(s)`;
      if (origin === "number" || origin === "int") return `Number must be ${exact ? "exactly equal to " : inclusive ? "greater than or equal to " : "greater than "}${minimum}`;
      return undefined;
    }
    case "too_big": {
      const { origin, maximum, inclusive, exact } = issue;
      if (origin === "array") return `Array must contain ${exact ? "exactly" : inclusive ? "at most" : "less than"} ${maximum} element(s)`;
      if (origin === "string") return `String must contain ${exact ? "exactly" : inclusive ? "at most" : "under"} ${maximum} character(s)`;
      if (origin === "number" || origin === "int") return `Number must be ${exact ? "exactly" : inclusive ? "less than or equal to" : "less than"} ${maximum}`;
      return undefined;
    }
    case "invalid_format": {
      switch (issue.format) {
        case "regex":
          return "Invalid";
        case "starts_with":
          return `Invalid input: must start with "${issue.prefix}"`;
        case "ends_with":
          return `Invalid input: must end with "${issue.suffix}"`;
        case "includes":
          return `Invalid input: must include "${issue.includes}"`;
        case "ipv4":
        case "ipv6":
          return "Invalid ip";
        default:
          return issue.format ? `Invalid ${issue.format}` : undefined;
      }
    }
    case "invalid_value": {
      const values = issue.values ?? [];
      if (issue.inst?._zod?.def?.type === "enum") {
        if (typeof issue.input !== "string") {
          return issue.input === undefined ? "Required" : `Expected ${joinValues(values)}, received ${receivedType(issue.input)}`;
        }
        return `Invalid enum value. Expected ${joinValues(values)}, received '${issue.input}'`;
      }
      return `Invalid literal value, expected ${JSON.stringify(values.length === 1 ? values[0] : values)}`;
    }
    case "not_multiple_of":
      return `Number must be a multiple of ${issue.divisor}`;
    case "unrecognized_keys":
      return `Unrecognized key(s) in object: ${(issue.keys ?? []).map((k) => `'${k}'`).join(", ")}`;
    default:
      return undefined;
  }
}

let installed = false;

export function installZodMessages(): void {
  if (installed) return;
  installed = true;
  z.config({ customError: (issue) => zodDefaultMessage(issue as unknown as RawIssue) });
}
