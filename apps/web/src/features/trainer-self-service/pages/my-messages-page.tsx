import { Paperclip, Send } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import {
  useConversationMessages,
  useMyConversations,
  useMyStudents,
  useOpenConversationWithStudent,
  useSendMessage,
} from "@/features/trainer-self-service/api/messaging-hooks";
import type { MessagePublic } from "@/features/trainer-self-service/api/messaging-api";
import { useAuthStore } from "@/store/auth-store";

function AttachmentPreview({ documentId }: { documentId: string }) {
  // Attachments are shown as a plain link -- resolving a presigned view
  // URL per attachment would need a dedicated download-url endpoint,
  // which isn't wired up in this first pass.
  return (
    <p className="text-xs italic text-muted-foreground">
      📎 Attachment ({documentId.slice(0, 8)}...)
    </p>
  );
}

function MessageBubble({ message, isMine }: { message: MessagePublic; isMine: boolean }) {
  return (
    <div className={`flex ${isMine ? "justify-end" : "justify-start"}`}>
      <div
        className={`max-w-[75%] rounded-lg px-3 py-2 text-sm ${
          isMine ? "bg-primary text-primary-foreground" : "bg-muted"
        }`}
      >
        {message.body && <p className="whitespace-pre-wrap">{message.body}</p>}
        {message.attachment_document_id && <AttachmentPreview documentId={message.attachment_document_id} />}
        <p className={`mt-1 text-[10px] ${isMine ? "text-primary-foreground/70" : "text-muted-foreground"}`}>
          {new Date(message.created_at).toLocaleString()}
        </p>
      </div>
    </div>
  );
}

function ConversationThread({ conversationId }: { conversationId: string }) {
  const currentUserId = useAuthStore((s) => s.user)?.id;
  const { data: messages, isLoading } = useConversationMessages(conversationId);
  const sendMessage = useSendMessage(conversationId);
  const [body, setBody] = useState("");
  const [attachment, setAttachment] = useState<File | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ block: "end" });
  }, [messages]);

  const handleSend = () => {
    if (!body.trim() && !attachment) return;
    sendMessage.mutate(
      { body: body.trim() || null, attachment: attachment ?? undefined },
      {
        onSuccess: () => {
          setBody("");
          setAttachment(null);
          if (fileInputRef.current) fileInputRef.current.value = "";
        },
      }
    );
  };

  return (
    <div className="flex h-full flex-col">
      <div className="flex-1 space-y-2 overflow-y-auto p-4">
        {isLoading && <Skeleton className="h-24 w-full" />}
        {!isLoading && (messages?.length ?? 0) === 0 && (
          <p className="text-center text-sm text-muted-foreground">No messages yet.</p>
        )}
        {messages?.map((m) => (
          <MessageBubble key={m.id} message={m} isMine={m.sender_user_id === currentUserId} />
        ))}
        <div ref={bottomRef} />
      </div>
      <div className="space-y-2 border-t p-3">
        {attachment && (
          <div className="flex items-center justify-between rounded-md border px-3 py-1.5 text-xs">
            <span className="truncate">{attachment.name}</span>
            <button className="text-muted-foreground hover:text-foreground" onClick={() => setAttachment(null)}>
              Remove
            </button>
          </div>
        )}
        {sendMessage.isError && (
          <p className="text-xs text-destructive">Could not send. Please try again.</p>
        )}
        <div className="flex items-end gap-2">
          <input
            ref={fileInputRef}
            type="file"
            accept="image/*,video/*"
            className="hidden"
            onChange={(e) => setAttachment(e.target.files?.[0] ?? null)}
          />
          <Button
            type="button"
            variant="outline"
            size="icon"
            onClick={() => fileInputRef.current?.click()}
            title="Attach a photo or video"
          >
            <Paperclip className="h-4 w-4" />
          </Button>
          <textarea
            value={body}
            onChange={(e) => setBody(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                handleSend();
              }
            }}
            placeholder="Reply to your student..."
            rows={1}
            className="flex-1 resize-none rounded-md border bg-background px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-ring"
          />
          <Button
            type="button"
            size="icon"
            onClick={handleSend}
            disabled={sendMessage.isPending || (!body.trim() && !attachment)}
          >
            <Send className="h-4 w-4" />
          </Button>
        </div>
      </div>
    </div>
  );
}

export function MyMessagesPage() {
  const { data: conversations, isLoading: conversationsLoading } = useMyConversations();
  const { data: students } = useMyStudents();
  const openConversation = useOpenConversationWithStudent();
  const [activeConversationId, setActiveConversationId] = useState<string | null>(null);

  const studentsWithoutConversation = (students ?? []).filter(
    (s) => !conversations?.some((c) => c.student_id === s.student_id)
  );

  const handleStartConversation = (studentId: string) => {
    openConversation.mutate(studentId, {
      onSuccess: (conversation) => setActiveConversationId(conversation.id),
    });
  };

  return (
    <div className="flex h-[calc(100vh-4rem)]">
      <div className="w-80 flex-shrink-0 border-r">
        <div className="border-b p-4">
          <h1 className="text-lg font-semibold">Messages</h1>
          <p className="text-xs text-muted-foreground">Chat with students in your batches.</p>
        </div>
        <div className="overflow-y-auto">
          {conversationsLoading && <Skeleton className="m-4 h-16 w-full" />}
          {conversations?.map((c) => (
            <button
              key={c.id}
              onClick={() => setActiveConversationId(c.id)}
              className={`flex w-full items-center justify-between border-b px-4 py-3 text-left text-sm hover:bg-muted ${
                activeConversationId === c.id ? "bg-muted" : ""
              }`}
            >
              <div className="min-w-0">
                <p className="truncate font-medium">{c.counterpart_name}</p>
                <p className="truncate text-xs text-muted-foreground">
                  {c.last_message?.body ?? (c.last_message ? "Sent an attachment" : "No messages yet")}
                </p>
              </div>
              {c.unread_count > 0 && <Badge variant="default">{c.unread_count}</Badge>}
            </button>
          ))}
          {studentsWithoutConversation.map((s) => (
            <button
              key={s.student_id}
              onClick={() => handleStartConversation(s.student_id)}
              className="flex w-full items-center border-b px-4 py-3 text-left text-sm text-muted-foreground hover:bg-muted"
            >
              {s.full_name}
              <span className="ml-auto text-xs">Start chat</span>
            </button>
          ))}
          {!conversationsLoading && (conversations?.length ?? 0) === 0 && studentsWithoutConversation.length === 0 && (
            <p className="p-4 text-sm text-muted-foreground">No students in your batches yet.</p>
          )}
        </div>
      </div>
      <div className="flex-1">
        {activeConversationId ? (
          <ConversationThread conversationId={activeConversationId} />
        ) : (
          <div className="flex h-full items-center justify-center text-sm text-muted-foreground">
            Select a conversation to start chatting.
          </div>
        )}
      </div>
    </div>
  );
}
