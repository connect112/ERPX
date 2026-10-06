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

// A line that starts a numbered question: "Q18.", "Q 18)", "Question 3:", "7."
const QUESTION_START_RE = /^\s*(?:Q(?:uestion)?\s*)?\d+\s*[.):]\s+\S/i;
const QUESTION_PREFIX_RE = /^\s*(?:Q(?:uestion)?\s*)?\d+\s*[.):]\s*/i;
// An option label: "A.", "A)", "(A)", optionally preceded by a star marking it correct.
const OPTION_LABEL_RE = /^\s*(\*\s*)?\(?([A-Ha-h])[.)]\s+(\*\s*)?(.*)$/;
// "Answer: C", "Answers: A, C", "Correct answer: B", "Ans - D"
const ANSWER_LINE_RE = /^\s*(?:correct\s+)?(?:answers?|ans)\s*[:=-]\s*(.+?)\s*$/i;
const LEGACY_LABEL_RE = /^(?:[A-Za-z]|\d{1,2})[).:]\s+/;

const MAX_OPTIONS = 8;

/** Trim blank lines off both ends and trailing spaces off every line, keeping indentation. */
function tidy(lines: string[]): string {
  const cleaned = lines.map((l) => l.replace(/\s+$/, ""));
  while (cleaned.length && !cleaned[0].trim()) cleaned.shift();
  while (cleaned.length && !cleaned[cleaned.length - 1].trim()) cleaned.pop();
  return cleaned.join("\n");
}

/**
 * Split pasted text into one chunk of lines per question. If any line looks like
 * a numbered question start ("Q1.", "2)") those lines are the boundaries, so a
 * question may contain blank lines (e.g. a code block). Otherwise questions are
 * separated by blank lines, as in the simple format.
 */
function splitBlocks(lines: string[]): string[][] {
  const hasNumbering = lines.some((l) => QUESTION_START_RE.test(l));
  const blocks: string[][] = [];
  let current: string[] = [];
  const flush = () => {
    if (current.some((l) => l.trim())) blocks.push(current);
    current = [];
  };
  let sawBlank = false;
  for (const line of lines) {
    if (hasNumbering) {
      if (QUESTION_START_RE.test(line)) flush();
      current.push(line);
    } else if (!line.trim()) {
      sawBlank = true;
    } else {
      if (sawBlank) flush();
      sawBlank = false;
      current.push(line);
    }
  }
  flush();
  return blocks;
}

function parseAnswerLetters(value: string): string[] | null {
  const tokens = value
    .toUpperCase()
    .split(/[\s,;&/]+|AND/)
    .map((t) => t.replace(/[().]/g, ""))
    .filter(Boolean);
  return tokens.length > 0 && tokens.every((t) => /^[A-H]$/.test(t)) ? tokens : null;
}

/** Labelled format: question text (any number of lines), then A./B./C. options (each may span lines). */
function parseLabelled(lines: string[], label: string): { row?: QuestionInput; error?: string } | null {
  // The options start at the first "A." line; later labels must follow in order.
  const firstA = lines.findIndex((l) => {
    const m = l.match(OPTION_LABEL_RE);
    return m && m[2].toUpperCase() === "A";
  });
  if (firstA < 0) return null;

  const questionLines = lines.slice(0, firstA);
  const options: string[][] = [];
  const correct = new Set<number>();
  let answerLetters: string[] | null = null;

  for (const line of lines.slice(firstA)) {
    const answer = line.match(ANSWER_LINE_RE);
    if (answer && parseAnswerLetters(answer[1])) {
      answerLetters = parseAnswerLetters(answer[1]);
      continue;
    }
    const m = line.match(OPTION_LABEL_RE);
    const expected = String.fromCharCode(65 + options.length);
    if (m && m[2].toUpperCase() === expected) {
      options.push([m[4]]);
      if (m[1] || m[3]) correct.add(options.length - 1);
    } else if (options.length > 0) {
      options[options.length - 1].push(line); // a continuation line of the current option
    }
  }

  const text = tidy(questionLines).replace(QUESTION_PREFIX_RE, "").trim();
  if (!text) return { error: `${label}: missing question text` };
  if (options.length < 2) return { error: `${label}: needs at least 2 options` };
  if (options.length > MAX_OPTIONS) return { error: `${label}: at most ${MAX_OPTIONS} options` };
  const optionTexts = options.map(tidy);
  if (optionTexts.some((o) => !o)) return { error: `${label}: has a blank option` };

  if (answerLetters) {
    for (const letter of answerLetters) {
      const index = letter.charCodeAt(0) - 65;
      if (index >= options.length) return { error: `${label}: the answer ${letter} has no matching option` };
      correct.add(index);
    }
  }
  if (correct.size < 1) {
    return { error: `${label}: mark the correct option with a leading * or add a line like "Answer: C"` };
  }
  const indices = [...correct].sort((a, b) => a - b);
  return {
    row: { text, options: optionTexts, correct_indices: indices, allow_multiple: indices.length > 1, marks: 1 },
  };
}

/** Simple format: first line is the question, each following line one option. */
function parseSimple(lines: string[], label: string): { row?: QuestionInput; error?: string } {
  const nonBlank = lines.map((l) => l.trim()).filter(Boolean);
  const questionText = (nonBlank[0] ?? "").replace(QUESTION_PREFIX_RE, "").trim();
  const optionLines = nonBlank.slice(1);
  if (!questionText) return { error: `${label}: missing question text` };
  if (optionLines.length < 2) return { error: `${label}: needs at least 2 options` };
  if (optionLines.length > MAX_OPTIONS) return { error: `${label}: at most ${MAX_OPTIONS} options` };
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
    rest = rest.replace(LEGACY_LABEL_RE, "").trim();
    if (rest.startsWith("*")) {
      isCorrect = true;
      rest = rest.slice(1).trim();
    }
    options.push(rest);
    if (isCorrect) correct.push(optionIndex);
  });
  if (options.some((o) => !o)) return { error: `${label}: has a blank option` };
  if (correct.length < 1) return { error: `${label}: mark the correct option with a leading *` };
  return {
    row: {
      text: questionText,
      options,
      correct_indices: correct,
      allow_multiple: correct.length > 1,
      marks: 1,
    },
  };
}

/**
 * Pasted questions. Two layouts are understood, per question:
 *
 * 1. Labelled (use this for code or multi-line text). The question is every
 *    line before "A.", each option starts with its letter and may continue on
 *    the following lines, and the correct one is marked with a leading * or an
 *    "Answer: C" line (several letters = pick-all-that-apply):
 *
 *      Q1. What does this print?
 *      print("hi")
 *      print("there")
 *      A. hi
 *      B. hi
 *         there
 *      Answer: B
 *
 * 2. Simple: first line is the question, then one option per line with a
 *    leading * on each correct one. Questions are separated by blank lines.
 */
export function parseQuestions(text: string): ParseResult<QuestionInput> {
  const rows: QuestionInput[] = [];
  const errors: string[] = [];
  const lines = text.replace(/^\uFEFF/, "").split(/\r?\n/).map((l) => l.replace(/\u00a0/g, " "));
  splitBlocks(lines).forEach((block, index) => {
    const label = `Question ${index + 1}`;
    const result = parseLabelled(block, label) ?? parseSimple(block, label);
    if (result.error) errors.push(result.error);
    else if (result.row) rows.push(result.row);
  });
  return { rows, errors };
}
