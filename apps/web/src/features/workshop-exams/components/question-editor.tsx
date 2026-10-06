import { Plus, X } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import type { QuestionInput } from "@/features/workshop-exams/api/workshop-exams-api";
import { questionProblem } from "@/features/workshop-exams/lib/question-draft";

/**
 * One question, edited the way a Google Forms quiz does it: type the
 * question, add as many options as you like, and tick which are correct --
 * a radio for "one right answer", checkboxes for "pick all that apply".
 */
export function QuestionEditor({
  initial,
  saveLabel,
  busy,
  error,
  onSave,
  onCancel,
}: {
  initial: QuestionInput;
  saveLabel: string;
  busy?: boolean;
  error?: string | null;
  onSave: (question: QuestionInput) => void;
  onCancel?: () => void;
}) {
  const [draft, setDraft] = useState<QuestionInput>(initial);
  const problem = questionProblem(draft);

  const setOption = (index: number, text: string) =>
    setDraft((d) => ({ ...d, options: d.options.map((o, i) => (i === index ? text : o)) }));

  const toggleCorrect = (index: number) =>
    setDraft((d) => {
      if (!d.allow_multiple) return { ...d, correct_indices: [index] };
      const has = d.correct_indices.includes(index);
      const next = has ? d.correct_indices.filter((i) => i !== index) : [...d.correct_indices, index];
      return { ...d, correct_indices: next.sort((a, b) => a - b) };
    });

  const removeOption = (index: number) =>
    setDraft((d) => ({
      ...d,
      options: d.options.filter((_, i) => i !== index),
      correct_indices: d.correct_indices.filter((i) => i !== index).map((i) => (i > index ? i - 1 : i)),
    }));

  const setMultiple = (allowMultiple: boolean) =>
    setDraft((d) => ({
      ...d,
      allow_multiple: allowMultiple,
      // Going back to one right answer keeps only the first tick.
      correct_indices: allowMultiple ? d.correct_indices : d.correct_indices.slice(0, 1),
    }));

  return (
    <div className="space-y-4 rounded-lg border bg-card p-4">
      <Textarea
        rows={Math.min(14, Math.max(3, draft.text.split("\n").length + 1))}
        value={draft.text}
        onChange={(e) => setDraft({ ...draft, text: e.target.value })}
        placeholder="Question"
        aria-label="Question"
      />
      <p className="-mt-2 text-xs text-muted-foreground">
        Line breaks are kept exactly as you type them. Put code between lines of three backticks (```) to show it in
        a code box.
      </p>

      <div className="flex flex-wrap items-center gap-3 text-sm">
        <label className="flex items-center gap-2">
          Answer type
          <select
            className="rounded-md border bg-background px-2 py-1"
            value={draft.allow_multiple ? "multiple" : "single"}
            onChange={(e) => setMultiple(e.target.value === "multiple")}
          >
            <option value="single">Multiple choice (one correct answer)</option>
            <option value="multiple">Checkboxes (several correct answers)</option>
          </select>
        </label>
        <label className="flex items-center gap-2">
          Marks
          <Input
            type="number"
            min={1}
            max={100}
            className="h-8 w-20"
            value={draft.marks}
            onChange={(e) => setDraft({ ...draft, marks: Math.max(1, Number(e.target.value) || 1) })}
          />
        </label>
      </div>

      <div className="space-y-2">
        <p className="text-xs text-muted-foreground">
          Tick {draft.allow_multiple ? "every correct answer" : "the correct answer"}.
        </p>
        {draft.options.map((option, index) => (
          <div key={index} className="flex items-start gap-2">
            <input
              type={draft.allow_multiple ? "checkbox" : "radio"}
              name="correct"
              checked={draft.correct_indices.includes(index)}
              onChange={() => toggleCorrect(index)}
              aria-label={`Option ${index + 1} is correct`}
            />
            <Textarea
              rows={Math.min(8, Math.max(1, option.split("\n").length))}
              className="min-h-0 resize-y py-2"
              value={option}
              onChange={(e) => setOption(index, e.target.value)}
              placeholder={`Option ${index + 1}`}
              aria-label={`Option ${index + 1}`}
            />
            <Button
              type="button"
              size="icon"
              variant="ghost"
              disabled={draft.options.length <= 2}
              onClick={() => removeOption(index)}
              aria-label={`Remove option ${index + 1}`}
            >
              <X className="h-4 w-4" />
            </Button>
          </div>
        ))}
        {draft.options.length < 8 && (
          <Button
            type="button"
            size="sm"
            variant="ghost"
            onClick={() => setDraft((d) => ({ ...d, options: [...d.options, ""] }))}
          >
            <Plus className="h-4 w-4" />
            Add option
          </Button>
        )}
      </div>

      {(problem || error) && <p className="text-sm text-destructive">{error ?? problem}</p>}
      <div className="flex gap-2">
        <Button disabled={!!problem || busy} onClick={() => onSave(draft)}>
          {busy ? "Saving..." : saveLabel}
        </Button>
        {onCancel && (
          <Button variant="outline" onClick={onCancel}>
            Cancel
          </Button>
        )}
      </div>
    </div>
  );
}
