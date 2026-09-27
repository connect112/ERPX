import { Search } from "lucide-react";
import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import {
  useAdminConversationMessages,
  useAdminConversationsList,
} from "@/features/messaging/api/messaging-hooks";
import type { MessagePublic } from "@/features/messaging/api/messaging-api";

function MessageBubble({ message }: { message: MessagePublic }) {
  return (
    <div className="rounded-lg border bg-card px-3 py-2 text-sm">
      {message.body && <p className="whitespace-pre-wrap">{message.body}</p>}
      {message.attachment_document_id && (
        <p className="text-xs italic text-muted-foreground">
          📎 Attachment ({message.attachment_document_id.slice(0, 8)}...)
        </p>
      )}
      <p className="mt-1 text-[10px] text-muted-foreground">
        {new Date(message.created_at).toLocaleString()}
      </p>
    </div>
  );
}

export function ConversationsPage() {
  const [search, setSearch] = useState("");
  const [activeConversationId, setActiveConversationId] = useState<string | null>(null);
  const { data, isLoading } = useAdminConversationsList({ limit: 100 });
  const { data: messages, isLoading: messagesLoading } = useAdminConversationMessages(
    activeConversationId ?? undefined
  );

  const filtered = (data?.items ?? []).filter((c) => {
    if (!search) return true;
    const needle = search.toLowerCase();
    return c.student_name.toLowerCase().includes(needle) || c.trainer_name.toLowerCase().includes(needle);
  });

  const active = filtered.find((c) => c.id === activeConversationId);

  return (
    <div className="space-y-6 p-8">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Student-Trainer Messages</h1>
        <p className="mt-1 text-muted-foreground">
          Read-only oversight of every doubt-clarification conversation. You cannot post into a
          conversation from here.
        </p>
      </div>

      <div className="flex h-[70vh] rounded-lg border">
        <div className="w-96 flex-shrink-0 border-r">
          <div className="border-b p-3">
            <div className="relative">
              <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
              <Input
                placeholder="Search by student or trainer..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="pl-8"
              />
            </div>
          </div>
          <div className="overflow-y-auto" style={{ maxHeight: "calc(70vh - 57px)" }}>
            {isLoading && <Skeleton className="m-4 h-16 w-full" />}
            {!isLoading && filtered.length === 0 && (
              <p className="p-4 text-sm text-muted-foreground">No conversations found.</p>
            )}
            {filtered.map((c) => (
              <button
                key={c.id}
                onClick={() => setActiveConversationId(c.id)}
                className={`flex w-full flex-col items-start border-b px-4 py-3 text-left text-sm hover:bg-muted ${
                  activeConversationId === c.id ? "bg-muted" : ""
                }`}
              >
                <span className="font-medium">
                  {c.student_name} <span className="text-muted-foreground">&harr;</span> {c.trainer_name}
                </span>
                <span className="mt-0.5 w-full truncate text-xs text-muted-foreground">
                  {c.last_message?.body ?? (c.last_message ? "Sent an attachment" : "No messages yet")}
                </span>
              </button>
            ))}
          </div>
        </div>
        <div className="flex-1">
          {active ? (
            <div className="flex h-full flex-col">
              <div className="border-b p-3">
                <p className="text-sm font-medium">
                  {active.student_name} <Badge variant="outline">Student</Badge> &harr; {active.trainer_name}{" "}
                  <Badge variant="outline">Trainer</Badge>
                </p>
              </div>
              <div className="flex-1 space-y-2 overflow-y-auto p-4">
                {messagesLoading && <Skeleton className="h-24 w-full" />}
                {messages?.map((m) => <MessageBubble key={m.id} message={m} />)}
                {!messagesLoading && (messages?.length ?? 0) === 0 && (
                  <p className="text-center text-sm text-muted-foreground">No messages yet.</p>
                )}
              </div>
            </div>
          ) : (
            <div className="flex h-full items-center justify-center text-sm text-muted-foreground">
              Select a conversation to view it.
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
