import { Fragment, useEffect, useState } from "react";

import { highlightCode } from "@/features/workshop-exams/lib/highlight";
import { splitSegments } from "@/features/workshop-exams/lib/segments";

function CodeBlock({ code, language }: { code: string; language: string }) {
  const [html, setHtml] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setHtml(null);
    void highlightCode(code, language).then((result) => {
      if (!cancelled) setHtml(result);
    });
    return () => {
      cancelled = true;
    };
  }, [code, language]);

  return (
    <pre className="code-block my-2 overflow-x-auto rounded-md border bg-muted/60 p-3 font-mono text-xs leading-relaxed">
      {html !== null ? (
        // highlight.js escapes the source before adding its <span> tags.
        <code className="hljs" dangerouslySetInnerHTML={{ __html: html }} />
      ) : (
        <code>{code}</code>
      )}
    </pre>
  );
}

/** Plain text with `inline code` shown in a monospace chip. Line breaks are kept. */
function Prose({ value }: { value: string }) {
  return (
    <span className="whitespace-pre-wrap">
      {value.split(/(`[^`\n]+`)/g).map((part, index) =>
        part.length > 2 && part.startsWith("`") && part.endsWith("`") ? (
          <code key={index} className="rounded bg-muted px-1 py-0.5 font-mono text-[0.85em]">
            {part.slice(1, -1)}
          </code>
        ) : (
          <Fragment key={index}>{part}</Fragment>
        )
      )}
    </span>
  );
}

/**
 * Question and option text exactly as typed: line breaks and indentation are
 * kept (plain text would collapse them), `inline code` gets a monospace chip,
 * and anything between ``` fences is shown as a syntax-highlighted code block
 * in the language written after the opening fence (```dockerfile).
 */
export function RichText({ text, className = "" }: { text: string; className?: string }) {
  return (
    <div className={`min-w-0 break-words ${className}`}>
      {splitSegments(text).map((segment, index) =>
        segment.kind === "code" ? (
          <CodeBlock key={index} code={segment.code} language={segment.language} />
        ) : segment.value ? (
          <Prose key={index} value={segment.value} />
        ) : null
      )}
    </div>
  );
}
