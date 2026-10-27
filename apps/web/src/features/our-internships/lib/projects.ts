import type { ProjectStatus, SubmissionMethod } from "@/features/our-internships/api/projects-api";

const EMAIL = /^[^@\s]+@[^@\s]+\.[^@\s]+$/;

/** What is wrong with the way a project is set up to be handed in, or null when it is fine. */
export function submissionProblem(v: {
  allowFile: boolean;
  allowEmail: boolean;
  allowRepo: boolean;
  email: string;
  startsAt: string;
  deadlineAt: string;
}): string | null {
  if (!v.allowFile && !v.allowEmail && !v.allowRepo) return "Allow at least one way of handing in: files, email or a repository link.";
  if (v.allowEmail && !EMAIL.test(v.email.trim())) return "Enter the email address students should send their work to.";
  if (v.startsAt && v.deadlineAt && new Date(v.deadlineAt) <= new Date(v.startsAt)) return "The deadline must be after the opening time.";
  return null;
}

export const PROJECT_STATUS: Record<ProjectStatus, { label: string; variant: "secondary" | "success" | "warning" }> = {
  draft: { label: "Draft", variant: "secondary" },
  published: { label: "Published", variant: "success" },
  closed: { label: "Closed", variant: "warning" },
};

export const METHOD_LABELS: Record<SubmissionMethod, string> = {
  file: "Files",
  email: "Email",
  repository: "Repository",
};

/** The ways a project accepts work, as a short list for a table cell. */
export function allowedMethods(p: { allow_file: boolean; allow_email: boolean; allow_repository: boolean }): string {
  return [p.allow_file && METHOD_LABELS.file, p.allow_email && METHOD_LABELS.email, p.allow_repository && METHOD_LABELS.repository].filter(Boolean).join(", ");
}
