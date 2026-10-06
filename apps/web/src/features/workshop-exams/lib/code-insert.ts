export interface EditResult {
  value: string;
  selectionStart: number;
  selectionEnd: number;
}

/**
 * Turn the selected lines into a fenced code block (```lang ... ```), or
 * insert an empty one with the caret inside when nothing is selected. Blank
 * lines are added around it when it would otherwise touch other text.
 */
export function insertCodeBlock(value: string, start: number, end: number, language: string): EditResult {
  const before = value.slice(0, start);
  const selected = value.slice(start, end).replace(/^\n+|\n+$/g, "");
  const after = value.slice(end);
  const lead = before.length > 0 && !before.endsWith("\n") ? "\n" : "";
  const trail = after.length > 0 && !after.startsWith("\n") ? "\n" : "";
  const open = "```" + language + "\n";
  const block = lead + open + selected + (selected ? "\n" : "\n") + "```" + trail;
  const next = before + block + after;
  if (!selected) {
    // Caret on the empty line between the fences, ready to type or paste.
    const caret = before.length + lead.length + open.length;
    return { value: next, selectionStart: caret, selectionEnd: caret };
  }
  const caret = before.length + block.length;
  return { value: next, selectionStart: caret, selectionEnd: caret };
}

/** Wrap the selection in single backticks (inline code); with no selection, insert a placeholder. */
export function insertInlineCode(value: string, start: number, end: number): EditResult {
  const selected = value.slice(start, end);
  if (!selected) {
    const next = value.slice(0, start) + "``" + value.slice(end);
    return { value: next, selectionStart: start + 1, selectionEnd: start + 1 };
  }
  const next = value.slice(0, start) + "`" + selected + "`" + value.slice(end);
  return { value: next, selectionStart: end + 2, selectionEnd: end + 2 };
}
