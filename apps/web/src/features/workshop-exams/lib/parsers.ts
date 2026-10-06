import type { AttendeeInput, QuestionInput } from "@/features/workshop-exams/api/workshop-exams-api";

const EMAIL_RE = /[^\s,;\t<>"']+@[^\s,;\t<>"']+\.[^\s,;\t<>"']+/;

export interface ParseResult<T> {
  rows: T[];
  errors: string[];
}

/**
 * One attendee per line. Accepts "Name, email", "Name<TAB>email" (pasted
 * straight from a spreadsheet) or "email Name" in either order -- the
 * email is whatever looks like one, the rest of the line is the name.
 */
export function parseAttendees(text: string): ParseResult<AttendeeInput> {
  const rows: AttendeeInput[] = [];
  const errors: string[] = [];
  text.split(/\r?\n/).forEach((raw, index) => {
    const line = raw.trim();
    if (!line) return;
    const match = line.match(EMAIL_RE);
    if (!match) {
      // A header row ("Name, Email") isn't an error worth reporting.
      if (!/^name\b/i.test(line)) errors.push(`Line ${index + 1}: no email found`);
      return;
    }
    const name = line
      .replace(match[0], "")
      .replace(/[,;\t"<>]+/g, " ")
      .replace(/\s+/g, " ")
      .trim();
    if (!name) {
      errors.push(`Line ${index + 1}: no name next to ${match[0]}`);
      return;
    }
    rows.push({ name, email: match[0].toLowerCase() });
  });
  return { rows, errors };
}

const OPTION_LABEL_RE = /^(?:[A-Za-z]|\d{1,2})[).:]\s+/;

/**
 * Questions separated by a blank line. First line is the question, each
 * following line an option, with a leading "*" on each correct one (more
 * than one star = a question where several answers must be picked):
 *
 *   What is 2 + 2?
 *   3
 *   *4
 *   5
 */
export function parseQuestions(text: string): ParseResult<QuestionInput> {
  const rows: QuestionInput[] = [];
  const errors: string[] = [];
  const blocks = text
    .split(/\r?\n\s*\r?\n/)
    .map((b) => b.trim())
    .filter(Boolean);
  blocks.forEach((block, index) => {
    const lines = block
      .split(/\r?\n/)
      .map((l) => l.trim())
      .filter(Boolean);
    const label = `Question ${index + 1}`;
    const questionText = lines[0].replace(/^(?:Q\s*\d*[).:]?|\d+[).:])\s*/i, "").trim();
    const optionLines = lines.slice(1);
    if (!questionText) {
      errors.push(`${label}: missing question text`);
      return;
    }
    if (optionLines.length < 2) {
      errors.push(`${label}: needs at least 2 options`);
      return;
    }
    if (optionLines.length > 8) {
      errors.push(`${label}: at most 8 options`);
      return;
    }
    const options: string[] = [];
    const correct: number[] = [];
    optionLines.forEach((optionLine, optionIndex) => {
      // The star may come before the label ("*B) 4") or after it ("B) *4").
      let rest = optionLine;
      let isCorrect = false;
      if (rest.startsWith("*")) {
        isCorrect = true;
        rest = rest.slice(1).trim();
      }
      rest = rest.replace(OPTION_LABEL_RE, "").trim();
      if (rest.startsWith("*")) {
        isCorrect = true;
        rest = rest.slice(1).trim();
      }
      options.push(rest);
      if (isCorrect) correct.push(optionIndex);
    });
    if (options.some((o) => !o)) {
      errors.push(`${label}: has a blank option`);
      return;
    }
    if (correct.length < 1) {
      errors.push(`${label}: mark the correct option with a leading *`);
      return;
    }
    // More than one starred option makes it a checkbox question.
    rows.push({
      text: questionText,
      options,
      correct_indices: correct,
      allow_multiple: correct.length > 1,
      marks: 1,
    });
  });
  return { rows, errors };
}
