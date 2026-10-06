import type { HLJSApi, LanguageFn } from "highlight.js";

/** Languages offered in the "Code block" menu (value = the tag written after the opening ```). */
export const CODE_LANGUAGES: { value: string; label: string }[] = [
  { value: "bash", label: "Bash / Shell" },
  { value: "dockerfile", label: "Dockerfile" },
  { value: "yaml", label: "YAML" },
  { value: "json", label: "JSON" },
  { value: "python", label: "Python" },
  { value: "java", label: "Java" },
  { value: "javascript", label: "JavaScript" },
  { value: "typescript", label: "TypeScript" },
  { value: "sql", label: "SQL" },
  { value: "xml", label: "HTML / XML" },
  { value: "css", label: "CSS" },
  { value: "c", label: "C" },
  { value: "cpp", label: "C++" },
  { value: "csharp", label: "C#" },
  { value: "go", label: "Go" },
  { value: "php", label: "PHP" },
  { value: "ruby", label: "Ruby" },
  { value: "rust", label: "Rust" },
  { value: "kotlin", label: "Kotlin" },
  { value: "powershell", label: "PowerShell" },
  { value: "nginx", label: "Nginx config" },
  { value: "ini", label: "INI / config" },
  { value: "plaintext", label: "Plain text (no colours)" },
];

// Each language is only downloaded the first time a question actually uses it.
const LOADERS: Record<string, () => Promise<{ default: LanguageFn }>> = {
  bash: () => import("highlight.js/lib/languages/bash"),
  dockerfile: () => import("highlight.js/lib/languages/dockerfile"),
  yaml: () => import("highlight.js/lib/languages/yaml"),
  json: () => import("highlight.js/lib/languages/json"),
  python: () => import("highlight.js/lib/languages/python"),
  java: () => import("highlight.js/lib/languages/java"),
  javascript: () => import("highlight.js/lib/languages/javascript"),
  typescript: () => import("highlight.js/lib/languages/typescript"),
  sql: () => import("highlight.js/lib/languages/sql"),
  xml: () => import("highlight.js/lib/languages/xml"),
  css: () => import("highlight.js/lib/languages/css"),
  c: () => import("highlight.js/lib/languages/c"),
  cpp: () => import("highlight.js/lib/languages/cpp"),
  csharp: () => import("highlight.js/lib/languages/csharp"),
  go: () => import("highlight.js/lib/languages/go"),
  php: () => import("highlight.js/lib/languages/php"),
  ruby: () => import("highlight.js/lib/languages/ruby"),
  rust: () => import("highlight.js/lib/languages/rust"),
  kotlin: () => import("highlight.js/lib/languages/kotlin"),
  powershell: () => import("highlight.js/lib/languages/powershell"),
  nginx: () => import("highlight.js/lib/languages/nginx"),
  ini: () => import("highlight.js/lib/languages/ini"),
};

const ALIASES: Record<string, string> = {
  docker: "dockerfile",
  sh: "bash",
  shell: "bash",
  zsh: "bash",
  console: "bash",
  js: "javascript",
  jsx: "javascript",
  ts: "typescript",
  tsx: "typescript",
  py: "python",
  yml: "yaml",
  html: "xml",
  "c++": "cpp",
  "c#": "csharp",
  cs: "csharp",
  golang: "go",
  ps1: "powershell",
  conf: "ini",
  toml: "ini",
  text: "plaintext",
  txt: "plaintext",
};

/** The language to use for a fence tag, or null when it should be shown as plain code. */
export function normalizeLanguage(tag: string): string | null {
  const key = tag.trim().toLowerCase();
  const language = ALIASES[key] ?? key;
  return language in LOADERS ? language : null;
}

let corePromise: Promise<HLJSApi> | null = null;
const registered = new Set<string>();

/**
 * Highlighted HTML for `code` (already HTML-escaped by highlight.js), or null
 * if the language is unknown/plain or loading failed -- callers then show the
 * code uncoloured, so a highlighting problem can never hide a question.
 */
export async function highlightCode(code: string, tag: string): Promise<string | null> {
  const language = normalizeLanguage(tag);
  if (!language) return null;
  try {
    corePromise ??= import("highlight.js/lib/core").then((m) => m.default);
    const core = await corePromise;
    if (!registered.has(language)) {
      core.registerLanguage(language, (await LOADERS[language]()).default);
      registered.add(language);
    }
    return core.highlight(code, { language, ignoreIllegals: true }).value;
  } catch {
    return null;
  }
}
