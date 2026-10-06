import { describe, expect, it } from "vitest";

import { parseAttendees, parseQuestions } from "@/features/workshop-exams/lib/parsers";

describe("parseAttendees", () => {
  it("accepts comma, tab and reversed layouts and lowercases emails", () => {
    const { rows, errors } = parseAttendees(
      "Name, Email\nAsha Rao, Asha@Example.com\nRavi Kumar\travi@example.com\nmeena@example.com Meena S\n"
    );
    expect(errors).toEqual([]);
    expect(rows).toEqual([
      { name: "Asha Rao", email: "asha@example.com" },
      { name: "Ravi Kumar", email: "ravi@example.com" },
      { name: "Meena S", email: "meena@example.com" },
    ]);
  });

  it("reports lines it cannot use without dropping the good ones", () => {
    const { rows, errors } = parseAttendees("Good Person, good@example.com\nno email here\nsolo@example.com");
    expect(rows).toHaveLength(1);
    expect(errors).toEqual(["Line 2: no email found", "Line 3: no name next to solo@example.com"]);
  });
});

describe("parseQuestions", () => {
  it("parses blocks, strips numbering and option labels, finds the starred answer", () => {
    const { rows, errors } = parseQuestions("Q1. What is 2 + 2?\nA) 3\nB) *4\nC) 5\n\n2) Capital of France?\n*Paris\nRome");
    expect(errors).toEqual([]);
    expect(rows).toEqual([
      { text: "What is 2 + 2?", options: ["3", "4", "5"], correct_indices: [1], allow_multiple: false, marks: 1 },
      { text: "Capital of France?", options: ["Paris", "Rome"], correct_indices: [0], allow_multiple: false, marks: 1 },
    ]);
  });

  it("flags a missing answer key instead of guessing", () => {
    const { rows, errors } = parseQuestions("No star?\nyes\nno");
    expect(rows).toEqual([]);
    expect(errors).toHaveLength(1);
    expect(errors[0]).toContain("Question 1");
  });

  it("treats several starred options as a pick-all-that-apply question", () => {
    const { rows, errors } = parseQuestions("Primes?\n*2\n*3\n4");
    expect(errors).toEqual([]);
    expect(rows[0]).toMatchObject({ correct_indices: [0, 1], allow_multiple: true });
  });
});
