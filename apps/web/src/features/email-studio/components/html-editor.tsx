import { html } from "@codemirror/lang-html";
import CodeMirror, { EditorView } from "@uiw/react-codemirror";
import { forwardRef, useImperativeHandle, useMemo, useRef } from "react";

import { useTheme } from "@/components/theme-provider";
import { htmlIssues } from "@/features/email-studio/lib/studio";

export interface HtmlEditorHandle {
  insertText: (text: string) => void;
}

/** The HTML source, with syntax highlighting and a quick check of the things that will be removed or are unclosed. */
export const HtmlEditor = forwardRef<HtmlEditorHandle, { value: string; onChange: (value: string) => void }>(function HtmlEditor({ value, onChange }, ref) {
  const view = useRef<EditorView | null>(null);
  const { theme } = useTheme();
  const issues = useMemo(() => htmlIssues(value), [value]);
  const dark = theme === "dark" || (theme === "system" && window.matchMedia("(prefers-color-scheme: dark)").matches);

  useImperativeHandle(ref, () => ({
    insertText(text: string) {
      const v = view.current;
      if (!v) return;
      const { from, to } = v.state.selection.main;
      v.dispatch({ changes: { from, to, insert: text }, selection: { anchor: from + text.length } });
      v.focus();
    },
  }));

  return (
    <div className="space-y-2">
      <div className="overflow-hidden rounded-md border">
        <CodeMirror
          value={value}
          height="calc(100vh - 20rem)"
          minHeight="420px"
          theme={dark ? "dark" : "light"}
          extensions={[html({ autoCloseTags: true }), EditorView.lineWrapping]}
          onCreateEditor={(v) => {
            view.current = v;
          }}
          onChange={onChange}
          basicSetup={{ lineNumbers: true, foldGutter: true, highlightActiveLine: true }}
          aria-label="HTML source"
        />
      </div>
      {issues.length > 0 && (
        <ul className="list-disc space-y-0.5 pl-5 text-xs text-amber-700 dark:text-amber-400" aria-label="HTML checks">
          {issues.map((i) => (
            <li key={i}>{i}</li>
          ))}
        </ul>
      )}
    </div>
  );
});

export default HtmlEditor;
