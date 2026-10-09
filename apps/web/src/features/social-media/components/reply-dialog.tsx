import { Sparkles } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import type { AiSuggestion, ReplyRecord, Triage } from "@/features/social-media/api/social-media-api";
import { useSendReply, useSuggest } from "@/features/social-media/api/social-media-hooks";
import { UnclearReply } from "@/features/social-media/components/inbox-parts";
import { errorMessage } from "@/features/social-media/lib/format";

export interface ReplyTarget {
  id: string;
  kind: "comment" | "dm";
  /** Who wrote to us. */
  from: string;
  /** What they wrote (a comment, or the latest message). */
  theirText: string;
  triage: Triage;
  suggestion: AiSuggestion;
}

const LIMIT = { comment: 2200, dm: 1000 } as const;

function newRequestId(): string {
  return (globalThis.crypto?.randomUUID?.() ?? `${Date.now()}${Math.random().toString(16).slice(2)}`).replace(/-/g, "");
}

/** Bytes, because Instagram limits a direct message in bytes (Hindi, emoji and other scripts are longer than they look). */
function byteLength(text: string): number {
  return new TextEncoder().encode(text).length;
}

interface Props {
  target: ReplyTarget | null;
  onClose: () => void;
  /** Called after a reply went out (or a result the person still has to settle), so the list can refresh. */
  onDone?: () => void;
}

/**
 * The only way a reply is ever sent. A person writes (or accepts and edits an AI draft), reviews the exact final text, and
 * presses Send once. Nothing here sends on its own, and the AI draft is only ever a starting point for the text box.
 */
export function ReplyDialog({ target, onClose, onDone }: Props) {
  const kind = target?.kind ?? "comment";
  const send = useSendReply(kind);
  const suggest = useSuggest(kind);
  const [text, setText] = useState("");
  const [fromSuggestion, setFromSuggestion] = useState(false);
  const [review, setReview] = useState(false);
  const [acknowledged, setAcknowledged] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<ReplyRecord | null>(null);
  const [suggestion, setSuggestion] = useState<AiSuggestion | null>(null);
  // One id per attempt a person makes: sending it twice (a double click, a retried request) can never post twice.
  const requestId = useRef(newRequestId());

  const id = target?.id;
  useEffect(() => {
    setText("");
    setFromSuggestion(false);
    setReview(false);
    setAcknowledged(false);
    setError(null);
    setResult(null);
    setSuggestion(target?.suggestion ?? null);
    requestId.current = newRequestId();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  if (!target) return null;
  const limit = LIMIT[target.kind];
  const size = target.kind === "dm" ? byteLength(text.trim()) : text.trim().length;
  const tooLong = size > limit;
  const needsAck = target.triage.needs_care;
  const canReview = text.trim().length > 0 && !tooLong && (!needsAck || acknowledged);
  const settled = result?.status === "sent";

  function ask() {
    if (!target) return;
    setError(null);
    suggest.mutate(target.id, {
      onSuccess: (data) => setSuggestion(data.suggestion),
      onError: (e) => setError(errorMessage(e, "Couldn't get a suggestion.")),
    });
  }

  function useDraft() {
    if (!suggestion?.reply) return;
    setText(suggestion.reply);
    setFromSuggestion(true);
    setReview(false);
  }

  function submit() {
    if (!target || send.isPending || settled) return;
    setError(null);
    send.mutate(
      { id: target.id, payload: { message: text, request_id: requestId.current, from_suggestion: fromSuggestion, acknowledge_sensitive: acknowledged } },
      {
        onSuccess: (reply) => {
          setResult(reply);
          // A certain failure is not a reason to be stuck on the same request: the next press is a new, deliberate attempt.
          if (reply.status === "failed") requestId.current = newRequestId();
          onDone?.();
        },
        onError: (e) => setError(errorMessage(e, "Couldn't send. Nothing was posted.")),
      },
    );
  }

  const unclear = result && (result.status === "unknown" || result.status === "pending");

  return (
    <Dialog open onOpenChange={(open) => !open && !send.isPending && onClose()}>
      <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-xl">
        <DialogHeader>
          <DialogTitle>{target.kind === "comment" ? "Reply to comment" : "Send a message"}</DialogTitle>
          <DialogDescription>
            {target.kind === "comment" ? "Your reply is public. It is posted only when you press Send." : "This is a private message. It is sent only when you press Send."}
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-3 text-sm">
          <blockquote className="rounded-md border-l-4 bg-muted/40 p-3">
            <p className="text-xs font-medium text-muted-foreground">@{target.from}</p>
            <p className="whitespace-pre-wrap break-words">{target.theirText}</p>
          </blockquote>

          {needsAck && (
            <div className="rounded-md border border-amber-300 bg-amber-50 p-3 text-amber-900">
              <p className="font-medium">Handle this one personally</p>
              <p>{target.triage.care_reason ?? "This looks sensitive."}</p>
              <label className="mt-2 flex items-start gap-2">
                <input type="checkbox" className="mt-1" checked={acknowledged} onChange={(e) => setAcknowledged(e.target.checked)} disabled={settled || review} />
                <span>I am handling this personally and will not rely on a canned answer.</span>
              </label>
            </div>
          )}

          {!settled && !unclear && (
            <>
              <div className="rounded-md border border-dashed p-3">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <p className="flex items-center gap-1 text-xs font-medium text-muted-foreground">
                    <Sparkles className="h-3.5 w-3.5" /> AI draft (a suggestion only, never sent by itself)
                  </p>
                  <Button type="button" size="sm" variant="outline" onClick={ask} disabled={suggest.isPending || send.isPending}>
                    {suggest.isPending ? "Thinking…" : suggestion?.at ? "Draft again" : "Suggest a reply"}
                  </Button>
                </div>
                {suggestion?.summary && <p className="mt-2 text-xs text-muted-foreground">Summary: {suggestion.summary}</p>}
                {suggestion?.reply ? (
                  <div className="mt-2 space-y-2">
                    <p className="whitespace-pre-wrap break-words rounded bg-muted/40 p-2">{suggestion.reply}</p>
                    <Button type="button" size="sm" variant="secondary" onClick={useDraft} disabled={send.isPending}>
                      Put this in the reply box
                    </Button>
                  </div>
                ) : (
                  suggestion?.note && <p className="mt-2 text-xs text-muted-foreground">{suggestion.note}</p>
                )}
              </div>

              {!review ? (
                <div className="space-y-1">
                  <Label htmlFor="sm-reply">Your reply</Label>
                  <Textarea
                    id="sm-reply"
                    rows={5}
                    value={text}
                    onChange={(e) => setText(e.target.value)}
                    placeholder="Write what you want to say."
                  />
                  <p className={`text-xs ${tooLong ? "text-destructive" : "text-muted-foreground"}`}>
                    {size} / {limit} {target.kind === "dm" ? "bytes" : "characters"}
                    {fromSuggestion ? " · started from an AI draft; you are responsible for the final words" : ""}
                  </p>
                </div>
              ) : (
                <div className="space-y-1">
                  <p className="text-xs font-medium text-muted-foreground">
                    {target.kind === "comment" ? `Will be posted publicly as a reply to @${target.from}:` : `Will be sent privately to @${target.from}:`}
                  </p>
                  <p className="whitespace-pre-wrap break-words rounded-md border-2 p-3" data-testid="final-text">
                    {text.trim()}
                  </p>
                </div>
              )}
            </>
          )}

          {settled && result && (
            <p role="status" className="rounded-md border border-emerald-300 bg-emerald-50 p-3 text-emerald-900">
              Sent{result.sent_by ? ` by ${result.sent_by}` : ""}. It is recorded in the reply history.
            </p>
          )}
          {result?.status === "failed" && (
            <p role="alert" className="rounded-md border border-destructive/40 bg-destructive/5 p-3 text-destructive">
              {result.error ?? "Not sent."}
            </p>
          )}
          {unclear && result && (
            <UnclearReply
              reply={result}
              onSettled={(reply) => {
                setResult(reply);
                // Proven not sent: the next press is a new, deliberate attempt (the old id would only return this record).
                if (reply.status === "failed") requestId.current = newRequestId();
                onDone?.();
              }}
            />
          )}
          {error && (
            <p role="alert" className="rounded-md border border-destructive/40 bg-destructive/5 p-3 text-destructive">
              {error}
            </p>
          )}
        </div>

        <DialogFooter className="gap-2 sm:gap-0">
          {settled || unclear ? (
            <Button onClick={onClose}>Close</Button>
          ) : review ? (
            <>
              <Button variant="outline" onClick={() => setReview(false)} disabled={send.isPending}>
                Back to editing
              </Button>
              <Button onClick={submit} disabled={send.isPending}>
                {send.isPending ? "Sending…" : target.kind === "comment" ? "Send reply now" : "Send message now"}
              </Button>
            </>
          ) : (
            <>
              <Button variant="outline" onClick={onClose}>
                Cancel
              </Button>
              <Button onClick={() => { setError(null); setResult(null); setReview(true); }} disabled={!canReview}>
                Review before sending
              </Button>
            </>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
