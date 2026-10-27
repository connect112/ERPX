import { describe, expect, it } from "vitest";

import { changeable, countsByKind, releaseSummary } from "@/features/our-internships/lib/certificates";

describe("countsByKind", () => {
  it("counts each list, and students without a choice in neither", () => {
    expect(countsByKind([{ kind: "participation" }, { kind: "completion" }, { kind: "completion" }, { kind: null }])).toEqual({ participation: 1, completion: 2 });
  });
});

describe("changeable", () => {
  const rows = [
    { selection_id: "a", locked: false },
    { selection_id: "b", locked: true },
    { selection_id: "c", locked: false },
  ];
  it("leaves out students whose certificate already exists and students not picked", () => {
    expect(changeable(rows, new Set(["a", "b"]))).toEqual(["a"]);
    expect(changeable(rows, new Set())).toEqual([]);
  });
});

describe("releaseSummary", () => {
  it("lists what will be sent", () => {
    expect(releaseSummary([{ label: "Participation", will_send: 3, already_sent: 0 }, { label: "Completion", will_send: 2, already_sent: 1 }])).toBe("3 participation, 2 completion (1 already sent)");
    expect(releaseSummary([])).toBe("Nothing to send");
  });
});
