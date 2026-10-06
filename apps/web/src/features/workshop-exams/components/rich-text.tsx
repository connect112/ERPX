import { Fragment } from "react";

/**
 * Question and option text exactly as typed: line breaks and indentation are
 * kept (plain text collapses them into one run-on line), and anything between
 * ``` fences is shown in a monospace box so code reads as code.
 */
export function RichText({ text, className = "" }: { text: string; className?: string }) {
  const parts = text.split(/(```[\s\S]*?```)/g);
  return (
    <div className={`min-w-0 break-words ${className}`}>
      {parts.map((part, index) => {
        if (part.startsWith("```") && part.endsWith("```") && part.length >= 6) {
          // Drop the fences and an optional language tag on the opening line.
          const code = part.slice(3, -3).replace(/^[^\n]*\n/, (first) => (first.trim() ? "" : first)).replace(/^\n|\n$/g, "");
          return (
            <pre key={index} className="my-2 overflow-x-auto rounded-md bg-muted p-3 font-mono text-xs leading-relaxed">
              <code>{code}</code>
            </pre>
          );
        }
        return part ? (
          <Fragment key={index}>
            <span className="whitespace-pre-wrap">{part}</span>
          </Fragment>
        ) : null;
      })}
    </div>
  );
}
