import { describe, expect, it } from "vitest";

import { insertCodeBlock, insertInlineCode } from "@/features/workshop-exams/lib/code-insert";
import { parseAttendees, parseQuestions } from "@/features/workshop-exams/lib/parsers";
import { splitSegments } from "@/features/workshop-exams/lib/segments";

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

  const DOCKERFILE_QUESTION = [
    "Q18. Making the Dockerfile safer",
    "The current Dockerfile of an application:",
    "FROM eclipse-temurin:21.0.2_13-jdk-jammy",
    "ENV DB_PASSWORD=Spring2026Pilot",
    "RUN apt-get update && apt-get install -y openssh-server sudo curl net-tools",
    "WORKDIR /app",
    "COPY . .",
    "RUN chmod -R 777 /app",
    "EXPOSE 8082 22",
    'CMD ["java", "-jar", "target/app.jar"]',
    "Which set of changes best reduces the attack surface without breaking the application?",
    "A. Keep the JDK image, change chmod -R 777 to chmod -R 755, keep SSH for troubleshooting, and",
    "turn the password into a build ARG so it is not in the final image.",
    "B. Switch to ubuntu:latest, install a JDK with apt, write USER root explicitly, and start the container",
    "with --privileged so it can use every system feature without restrictions.",
    "C. Use eclipse-temurin:21-jre-alpine; copy only the jar instead of COPY . .; remove SSH, sudo, extra",
    "tools and port 22; run as a non-root user; pass the password with docker run -e; add a",
    "HEALTHCHECK.",
    "D. Keep everything as it is and only add a .dockerignore file, because ignoring files is enough to",
    "remove the unwanted packages and the password from the image, even from the RUN and ENV",
    "lines.",
    "Answer: C",
  ].join("\n");

  it("keeps a multi-line code question as one question, with line breaks, and wrapped options as one option each", () => {
    const { rows, errors } = parseQuestions(DOCKERFILE_QUESTION);
    expect(errors).toEqual([]);
    expect(rows).toHaveLength(1);
    const q = rows[0];
    expect(q.options).toHaveLength(4);
    expect(q.correct_indices).toEqual([2]);
    expect(q.allow_multiple).toBe(false);
    // The heading's number is dropped; every code line stays on its own line.
    expect(q.text.startsWith("Making the Dockerfile safer\nThe current Dockerfile of an application:\nFROM eclipse")).toBe(true);
    expect(q.text).toContain("ENV DB_PASSWORD=Spring2026Pilot\nRUN apt-get update");
    expect(q.text.endsWith("without breaking the application?")).toBe(true);
    // A wrapped option stays one option, joined with its line break.
    expect(q.options[0]).toBe(
      "Keep the JDK image, change chmod -R 777 to chmod -R 755, keep SSH for troubleshooting, and\nturn the password into a build ARG so it is not in the final image."
    );
    expect(q.options[2].endsWith("add a\nHEALTHCHECK.")).toBe(true);
  });

  it("reads several numbered questions, even when a question contains a blank line", () => {
    const text = [
      "1. What does this print?",
      "x = 1",
      "",
      "print(x)",
      "A. 1",
      "B. 2",
      "Answer: A",
      "",
      "2. Capital of France?",
      "A) Rome",
      "B) *Paris",
      "",
      "Q3. Pick the primes",
      "A. 2",
      "B. 3",
      "C. 4",
      "Answers: A, B",
    ].join("\n");
    const { rows, errors } = parseQuestions(text);
    expect(errors).toEqual([]);
    expect(rows.map((r) => r.text)).toEqual(["What does this print?\nx = 1\n\nprint(x)", "Capital of France?", "Pick the primes"]);
    expect(rows[0].correct_indices).toEqual([0]);
    expect(rows[1].correct_indices).toEqual([1]);
    expect(rows[2]).toMatchObject({ correct_indices: [0, 1], allow_multiple: true });
  });

  it("accepts a star before or after the label, and lower-case answer lines", () => {
    const text = "Q1. Pick one\n*A. yes\nB. no\n\nQ2. Another\nA. yes\nB. no\nanswer: b";
    const { rows, errors } = parseQuestions(text);
    expect(errors).toEqual([]);
    expect(rows.map((r) => r.correct_indices)).toEqual([[0], [1]]);
  });

  it("keeps indentation inside code and survives pasted non-breaking spaces and Windows line endings", () => {
    const text = "Q1. Fix it\r\ndef f():\r\n    return 1\r\nA. yes\r\nB. no\r\nAnswer: A";
    const { rows, errors } = parseQuestions(text);
    expect(errors).toEqual([]);
    expect(rows[0].text).toBe("Fix it\ndef f():\n    return 1");
    expect(rows[0].options).toEqual(["yes", "no"]);
  });

  it("explains what is wrong with a labelled question instead of guessing", () => {
    expect(parseQuestions("Q1. Pick\nA. yes\nB. no").errors[0]).toContain('"Answer: C"');
    expect(parseQuestions("Q1. Pick\nA. yes\nB. no\nAnswer: D").errors[0]).toContain("answer D has no matching option");
    expect(parseQuestions("Q1. Pick\nA. only one\nAnswer: A").errors[0]).toContain("at least 2 options");
    expect(parseQuestions("A. yes\nB. no\nAnswer: A").errors[0]).toContain("missing question text");
  });
});

describe("code fences in pasted questions", () => {
  it("never reads structure inside a fence: A./B. lines, Answer: lines and numbered lines in code stay code", () => {
    const text = [
      "Q1. What does this script print?",
      "```bash",
      "1. first step",
      "A. not an option",
      "Answer: Z",
      "echo hello",
      "```",
      "A. hello",
      "B. goodbye",
      "Answer: A",
      "",
      "Q2. Another",
      "A. yes",
      "B. no",
      "Answer: B",
    ].join("\n");
    const { rows, errors } = parseQuestions(text);
    expect(errors).toEqual([]);
    expect(rows).toHaveLength(2);
    expect(rows[0].text).toBe(
      "What does this script print?\n```bash\n1. first step\nA. not an option\nAnswer: Z\necho hello\n```"
    );
    expect(rows[0].options).toEqual(["hello", "goodbye"]);
    expect(rows[0].correct_indices).toEqual([0]);
    expect(rows[1].text).toBe("Another");
  });

  it("allows a fenced code block inside an option", () => {
    const text = [
      "Q1. Which Dockerfile is safest?",
      "A. This one:",
      "```dockerfile",
      "FROM alpine",
      "USER app",
      "```",
      "B. This one:",
      "```dockerfile",
      "FROM ubuntu",
      "USER root",
      "```",
      "Answer: A",
    ].join("\n");
    const { rows, errors } = parseQuestions(text);
    expect(errors).toEqual([]);
    expect(rows[0].options).toEqual([
      "This one:\n```dockerfile\nFROM alpine\nUSER app\n```",
      "This one:\n```dockerfile\nFROM ubuntu\nUSER root\n```",
    ]);
  });

  it("keeps blank lines inside a fenced block even in the simple (unnumbered) format", () => {
    const { rows, errors } = parseQuestions("Q. What?\n```\na\n\nb\n```\n*x\ny");
    // The simple format drops blank lines per line, but the fence must not split the question in two.
    expect(rows.length + errors.length).toBe(1);
  });
});

describe("segments", () => {
  it("splits prose from fenced code and reads the language tag", () => {
    expect(splitSegments("Before\n```dockerfile\nFROM x\nRUN y\n```\nAfter")).toEqual([
      { kind: "text", value: "Before\n" },
      { kind: "code", language: "dockerfile", code: "FROM x\nRUN y" },
      { kind: "text", value: "\nAfter" },
    ]);
    expect(splitSegments("```\nplain\n```")).toEqual([{ kind: "code", language: "", code: "plain" }]);
    // An unclosed fence is just text, so a typo never swallows the question.
    expect(splitSegments("```bash\nnever closed")).toEqual([{ kind: "text", value: "```bash\nnever closed" }]);
  });
});

describe("code insert helpers", () => {
  it("wraps the selected lines in a fence and puts a blank line between prose and code", () => {
    const value = "Intro\nFROM x\nRUN y\nWhich is right?";
    const start = value.indexOf("FROM");
    const end = value.indexOf("\nWhich");
    const result = insertCodeBlock(value, start, end, "dockerfile");
    expect(result.value).toBe("Intro\n```dockerfile\nFROM x\nRUN y\n```\nWhich is right?");
  });

  it("inserts an empty fenced block with the caret inside when nothing is selected", () => {
    const result = insertCodeBlock("Question: ", 10, 10, "python");
    expect(result.value).toBe("Question: \n```python\n\n```");
    expect(result.value.slice(result.selectionStart - 10, result.selectionStart)).toBe("```python\n");
  });

  it("wraps a selected word in backticks, or inserts an empty pair", () => {
    expect(insertInlineCode("run chmod now", 4, 9).value).toBe("run `chmod` now");
    const empty = insertInlineCode("run ", 4, 4);
    expect(empty.value).toBe("run ``");
    expect(empty.selectionStart).toBe(5);
  });
});
