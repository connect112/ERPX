const EMAIL = /^\S+@\S+\.\S+$/;

/** Whether the add/edit form can be saved: a name, an email, a sensible score (or none) and an event. */
export function validStudent(v: { name: string; email: string; score: string; event: string }): boolean {
  if (!v.name.trim() || !EMAIL.test(v.email.trim()) || !v.event) return false;
  if (v.score.trim() === "") return true;
  const n = Number(v.score);
  return Number.isFinite(n) && n >= 0 && n <= 9999;
}
