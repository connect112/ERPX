import { redo, undo } from "@codemirror/commands";
import { javascript } from "@codemirror/lang-javascript";
import { type Diagnostic, lintGutter, setDiagnostics } from "@codemirror/lint";
import CodeMirror, { EditorView } from "@uiw/react-codemirror";
import { forwardRef, useEffect, useImperativeHandle, useRef } from "react";

import { useTheme } from "@/components/theme-provider";
import type { ReactIssue } from "@/features/email-studio/api/studio-api";

export interface ReactEditorHandle {
  insertText: (text: string) => void;
  /** Put the cursor at the start of a line and scroll to it. */
  goToLine: (line: number) => void;
  undo: () => void;
  redo: () => void;
  focus: () => void;
}

interface Props {
  value: string;
  onChange: (value: string) => void;
  /** Errors and warnings from the last build; each is marked on its line. */
  issues: ReactIssue[];
  readOnly?: boolean;
  /** Any CSS height; "100%" fills a parent that has a height. */
  height?: string;
  minHeight?: string;
}

/**
 * The React Email source (TSX) with syntax highlighting, line numbers, auto-indent, undo/redo and the server's findings marked on the
 * lines they belong to. Nothing typed here is ever run: it is only sent to the server to be read.
 */
export const ReactEditor = forwardRef<ReactEditorHandle, Props>(function ReactEditor({ value, onChange, issues, readOnly, height = "100%", minHeight = "320px" }, ref) {
  const view = useRef<EditorView | null>(null);
  const { theme } = useTheme();
  const dark = theme === "dark" || (theme === "system" && window.matchMedia("(prefers-color-scheme: dark)").matches);

  useImperativeHandle(ref, () => ({
    insertText(text: string) {
      const v = view.current;
      if (!v) return;
      const { from, to } = v.state.selection.main;
      v.dispatch({ changes: { from, to, insert: text }, selection: { anchor: from + text.length } });
      v.focus();
    },
    goToLine(line: number) {
      const v = view.current;
      if (!v) return;
      const target = v.state.doc.line(Math.min(Math.max(line, 1), v.state.doc.lines));
      v.dispatch({ selection: { anchor: target.from }, effects: EditorView.scrollIntoView(target.from, { y: "center" }) });
      v.focus();
    },
    undo: () => {
      if (view.current) undo(view.current);
    },
    redo: () => {
      if (view.current) redo(view.current);
    },
    focus: () => view.current?.focus(),
  }));

  useEffect(() => {
    const v = view.current;
    if (!v) return;
    const lines = v.state.doc.lines;
    const diagnostics: Diagnostic[] = issues
      .filter((i) => i.line && i.line >= 1 && i.line <= lines)
      .map((i) => {
        const line = v.state.doc.line(i.line as number);
        const from = Math.min(line.from + Math.max((i.column ?? 1) - 1, 0), line.to);
        return { from, to: Math.max(line.to, from), severity: i.severity, message: i.message };
      });
    v.dispatch(setDiagnostics(v.state, diagnostics));
  }, [issues, value]);

  return (
    <div className="h-full min-h-0 overflow-hidden rounded-md border" data-testid="react-editor">
      <CodeMirror
        value={value}
        height={height}
        minHeight={minHeight}
        theme={dark ? "dark" : "light"}
        readOnly={readOnly}
        editable={!readOnly}
        extensions={[javascript({ jsx: true, typescript: true }), lintGutter(), EditorView.lineWrapping]}
        onCreateEditor={(v) => {
          view.current = v;
        }}
        onChange={onChange}
        basicSetup={{ lineNumbers: true, foldGutter: true, highlightActiveLine: true, indentOnInput: true, bracketMatching: true, closeBrackets: true, history: true }}
        aria-label="React Email source code"
      />
    </div>
  );
});

export default ReactEditor;
