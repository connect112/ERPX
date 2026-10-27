import { describe, expect, it } from "vitest";

import type { StudentPerformance } from "@/features/our-internships/api/our-internships-api";

import { formatMarks, formatScore, formatTeamScore, selectableIds, sortStudents } from "./performance";

function student(over: Partial<StudentPerformance> & { name: string }): StudentPerformance {
  return {
    student_id: over.name,
    email: `${over.name.toLowerCase()}@example.com`,
    phone: null,
    details: {},
    institution_id: "i1",
    institution_name: "College",
    event_id: "e1",
    event_name: "Workshop",
    individual_score: null,
    remarks: null,
    exams: [],
    exam_score: null,
    exam_total: null,
    exam_percent: null,
    team: null,
    selected: false,
    ...over,
  };
}

const team = (score: number, tasks_scored = 1) => ({
  team_id: "t",
  team_name: "T",
  hackathon_id: "h",
  hackathon_title: "H",
  score,
  max_total: 100,
  rank: 1,
  tasks_scored,
});

describe("formatters", () => {
  it("formats marks, with a dash when there are none", () => {
    expect(formatMarks(8, 10, 80)).toBe("8 / 10 (80%)");
    expect(formatMarks(8, 10)).toBe("8 / 10");
    expect(formatMarks(8, null)).toBe("8");
    expect(formatMarks(null, 10)).toBe("—");
  });

  it("formats a team's score and rank", () => {
    expect(formatTeamScore(80, 100, 1)).toBe("80 / 100 · #1");
    expect(formatTeamScore(80, 0, null)).toBe("80");
    expect(formatTeamScore(null, 100, null)).toBe("—");
  });

  it("shows a zero score as 0, not as missing", () => {
    expect(formatScore(0)).toBe("0");
    expect(formatScore(null)).toBe("—");
    expect(formatMarks(0, 10, 0)).toBe("0 / 10 (0%)");
  });
});

describe("sortStudents", () => {
  const rows = [
    student({ name: "Cara", exam_percent: 40, individual_score: 5, team: team(60) }),
    student({ name: "Asha", exam_percent: 80, individual_score: null, team: team(90) }),
    student({ name: "Bela", exam_percent: null, individual_score: 9, team: null }),
    student({ name: "Dev", exam_percent: 80, individual_score: 7, team: team(0, 0) }),
  ];

  it("sorts best first, and puts people with no value for that column last either way", () => {
    expect(sortStudents(rows, "exam", "desc").map((r) => r.name)).toEqual(["Asha", "Dev", "Cara", "Bela"]);
    expect(sortStudents(rows, "exam", "asc").map((r) => r.name)).toEqual(["Cara", "Asha", "Dev", "Bela"]);
    expect(sortStudents(rows, "individual", "desc").map((r) => r.name)).toEqual(["Bela", "Dev", "Cara", "Asha"]);
  });

  it("does not treat a team that was never scored as a team that scored 0", () => {
    expect(sortStudents(rows, "team_score", "desc").map((r) => r.name)).toEqual(["Asha", "Cara", "Bela", "Dev"]);
  });

  it("breaks ties by name, and sorts by name", () => {
    expect(sortStudents(rows, "name", "asc").map((r) => r.name)).toEqual(["Asha", "Bela", "Cara", "Dev"]);
    expect(sortStudents(rows, "exam", "desc").slice(0, 2).map((r) => r.name)).toEqual(["Asha", "Dev"]);
  });

  it("does not change the list it was given", () => {
    const before = rows.map((r) => r.name);
    sortStudents(rows, "name", "desc");
    expect(rows.map((r) => r.name)).toEqual(before);
  });
});

describe("selectableIds", () => {
  it("lists each person once and leaves out the ones already selected", () => {
    const rows = [
      student({ name: "Asha" }),
      { ...student({ name: "Asha" }), event_id: "e2" }, // same person, second event
      student({ name: "Bela", selected: true }),
      student({ name: "Cara" }),
    ];
    expect(selectableIds(rows)).toEqual(["Asha", "Cara"]);
  });
});
