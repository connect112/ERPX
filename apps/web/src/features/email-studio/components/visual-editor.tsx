import "@react-email/editor/themes/default.css";
import "@react-email/editor/styles/bubble-menu.css";
import "@react-email/editor/styles/slash-command.css";
import "@react-email/editor/styles/inspector.css";

import { EmailEditor, type EmailEditorRef } from "@react-email/editor";
import { Inspector } from "@react-email/editor/ui";
import { type ComponentType, forwardRef, useImperativeHandle, useRef, useState } from "react";

import { studioApi, type EditorDoc } from "@/features/email-studio/api/studio-api";
import { EMPTY_DOC } from "@/features/email-studio/lib/studio";

// The editor ships its own undo/redo extension, but its type definitions do not declare the commands.
type History = { undo: () => { run: () => boolean }; redo: () => { run: () => boolean } };
type CanHistory = { undo: () => boolean; redo: () => boolean };
// Declared as a component that returns a bigint, which React 18's types reject; it renders normally.
const Breadcrumb = Inspector.Breadcrumb as unknown as ComponentType;

export interface VisualEditorHandle {
  /** The design as the editor's document and as email HTML, for saving and previewing. */
  snapshot: () => Promise<{ editor_json: EditorDoc; html: string }>;
  undo: () => void;
  redo: () => void;
  canUndo: () => boolean;
  canRedo: () => boolean;
  /** Type text (a placeholder) where the cursor is. */
  insertText: (text: string) => void;
  focus: () => void;
}

interface Props {
  content: EditorDoc | null;
  theme: Parameters<typeof EmailEditor>[0]["theme"];
  onChange: () => void;
}

/**
 * The React Email visual editor with its inspector. It keeps the design as the editor's own JSON (so it can be reopened and
 * edited) and exports email HTML on request. Images dropped or pasted in are uploaded and served from a public link.
 * Shown on a light canvas whatever the admin theme: it is a picture of the email.
 */
export const VisualEditor = forwardRef<VisualEditorHandle, Props>(function VisualEditor({ content, theme, onChange }, ref) {
  const editor = useRef<EmailEditorRef | null>(null);
  const [, setTick] = useState(0);

  useImperativeHandle(
    ref,
    () => ({
      async snapshot() {
        const current = editor.current;
        if (!current) throw new Error("The editor is not ready yet.");
        const { html } = await current.getEmail();
        return { editor_json: current.getJSON() as EditorDoc, html };
      },
      undo: () => void (editor.current?.editor?.chain().focus() as unknown as History | undefined)?.undo().run(),
      redo: () => void (editor.current?.editor?.chain().focus() as unknown as History | undefined)?.redo().run(),
      canUndo: () => (editor.current?.editor?.can() as unknown as CanHistory | undefined)?.undo() ?? false,
      canRedo: () => (editor.current?.editor?.can() as unknown as CanHistory | undefined)?.redo() ?? false,
      insertText: (text: string) => void editor.current?.editor?.chain().focus().insertContent(text).run(),
      focus: () => void editor.current?.editor?.commands.focus(),
    }),
    [],
  );

  return (
    <div className="flex h-[70vh] min-h-[420px] overflow-hidden rounded-md border bg-white text-gray-900 xl:h-full">
      <EmailEditor
        ref={editor}
        content={(content ?? EMPTY_DOC) as never}
        theme={theme}
        className="min-w-0 flex-1 overflow-y-auto p-4"
        onReady={(r) => {
          editor.current = r;
          setTick((n) => n + 1);
        }}
        onUpdate={(r) => {
          editor.current = r;
          onChange();
          setTick((n) => n + 1); // keeps the undo and redo buttons current
        }}
        onUploadImage={async (file) => {
          const asset = await studioApi.uploadAsset(file, "image");
          if (!asset.url) throw new Error("The image could not be hosted.");
          return { url: asset.url };
        }}
      >
        <Inspector.Root className="w-72 shrink-0 overflow-y-auto border-l bg-white p-4">
          <Breadcrumb />
          <Inspector.Document />
          <Inspector.Node />
          <Inspector.Text />
        </Inspector.Root>
      </EmailEditor>
    </div>
  );
});

export default VisualEditor;
