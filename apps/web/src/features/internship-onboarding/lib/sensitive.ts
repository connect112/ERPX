/** What the Documents settings tell an administrator about the Sensitive option. Nothing here relaxes a rule: the server enforces all of them. */
export const sensitiveHelp = {
  unavailable:
    "Sensitive documents (identity documents such as Aadhaar) cannot be turned on yet: this ERPX installation has no virus scanner. " +
    "They are only accepted when every upload is scanned, and this cannot be switched on from this page. Ask the person who runs the " +
    "server to set up the ClamAV scanner and enable virus scanning; until then, collect identity documents outside the portal.",
  disabledHere: "Sensitive is unavailable until virus scanning is set up (see the note above).",
  needsRetention: "Sensitive is on: set how long identity documents are kept under Policies before saving.",
  aadhaar: "This looks like an Aadhaar or identity document: it must be marked Sensitive.",
  on: "Sensitive: scanned on upload, masked in lists, and only reviewers can open it.",
  off: "Not sensitive: any reviewer can open it and it is kept like other documents.",
} as const;

/** Mirrors the server's rule that an Aadhaar document has to be marked sensitive. */
export function isIdentityDocument(doc: { key: string; label: string }): boolean {
  return /aadh?aa?r/i.test(`${doc.key} ${doc.label}`);
}
