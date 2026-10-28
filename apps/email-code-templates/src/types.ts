export type PropType = "text" | "textarea" | "url" | "color";

export interface PropDef {
  name: string;
  label: string;
  type: PropType;
  default: string;
  required?: boolean;
  description?: string;
}

/** What a template tells the API about itself; written to manifest.json by the build. */
export interface TemplateMeta {
  key: string;
  name: string;
  description: string;
  category: string;
  module: string | null;
  /** The ERPX email (a key of the built-in list) this template is written to replace. */
  suggested_for: string | null;
  subject: string;
  props: PropDef[];
  /** ERPX placeholders the template uses, besides its properties. */
  placeholders: string[];
}

export type Props = Record<string, string>;
