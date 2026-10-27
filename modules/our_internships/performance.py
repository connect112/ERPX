"""
How the students of an event performed, assembled for choosing who to select for an internship.

Nothing here is stored. Each time it is asked for, it reads the event's registration list, the workshop exams linked to the
event (marks by email), and the hackathons linked to the event (team scores from the scored tasks, team members by email),
so the numbers on screen are the live ones.

Matching is by lower-cased email: an exam attendee, a hackathon participant and a registration-list student are the same
person when their email is the same. A team member whose email is not on the event's registration list still appears in
the team (so the team is complete) but cannot be selected from here.
"""

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from modules.hackathons.models import Hackathon, ProblemStatement, TaskSubmission, Team
from modules.hackathons.models import TeamMember as HackathonTeamMember
from modules.institutions.models import EventRegistration, Institution, InstitutionEvent, InstitutionStudent
from modules.our_internships.schemas import (
    ExamInfo,
    ExamMark,
    HackathonInfo,
    PerformanceResponse,
    StudentPerformance,
    TeamMember,
    TeamPerformance,
    TeamRef,
)
from modules.students.models import Student
from modules.workshop_exams.models import WorkshopExam, WorkshopExamAttendee, WorkshopExamQuestion

NO_TEAM = "Not in a team"


def _matches(term: str | None, *texts: str | None) -> bool:
    if not term or not term.strip():
        return True
    needle = term.strip().lower()
    return any(needle in (t or "").lower() for t in texts)


class PerformanceBuilder:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def build(
        self,
        organization_id: uuid.UUID,
        *,
        institution_id: uuid.UUID | None = None,
        event_id: uuid.UUID | None = None,
        q: str | None = None,
        only_student_ids: set[uuid.UUID] | None = None,
        selected_ids: set[uuid.UUID] | frozenset = frozenset(),
        include_teams: bool = True,
    ) -> PerformanceResponse:
        pool = await self._registrations(organization_id, institution_id, event_id, only_student_ids)
        event_ids = sorted({event.id for _, _, event, _ in pool}, key=str)

        exams, exam_totals, exam_marks = await self._exam_marks(event_ids)
        hackathons, teams, team_members = await self._hackathons(event_ids)

        # a student's team in each event (the best-scoring one if, unusually, there are several hackathons)
        team_of: dict[tuple[uuid.UUID, str], TeamRef] = {}
        for team in teams.values():
            for email in (m[1] for m in team_members.get(team.team_id, []) if m[1]):
                key = (hackathons[team.hackathon_id].event_id, email)
                if key not in team_of or team.score > team_of[key].score:
                    team_of[key] = team

        students: list[StudentPerformance] = []
        by_event_email: dict[tuple[uuid.UUID, str], StudentPerformance] = {}
        for registration, student, event, institution in pool:
            marks = exam_marks.get((event.id, student.email), [])
            sat = [m for m in marks if m.attended and m.score is not None]
            exam_score = sum(m.score or 0 for m in sat) if sat else None
            exam_total = sum(m.total_marks or 0 for m in sat) if sat else None
            row = StudentPerformance(
                student_id=student.id,
                name=student.name,
                email=student.email,
                phone=student.phone,
                details=student.details or {},
                institution_id=institution.id,
                institution_name=institution.name,
                event_id=event.id,
                event_name=event.name,
                individual_score=float(registration.individual_score) if registration.individual_score is not None else None,
                remarks=registration.remarks,
                exams=exam_marks.get((event.id, student.email))
                or [ExamMark(exam_id=x.id, title=x.title, attended=False) for x in exams if x.event_id == event.id],
                exam_score=exam_score,
                exam_total=exam_total,
                exam_percent=round(100 * exam_score / exam_total, 1) if exam_score is not None and exam_total else None,
                team=team_of.get((event.id, student.email)),
                selected=student.id in selected_ids,
            )
            by_event_email[(event.id, student.email)] = row
            students.append(row)

        team_rows: list[TeamPerformance] = []
        if include_teams:
            team_rows = self._team_rows(pool, hackathons, teams, team_members, by_event_email, students, selected_ids)

        shown = [s for s in students if _matches(q, s.name, s.email, s.phone, s.team.team_name if s.team else None)]
        if q and q.strip():
            team_rows = [
                t
                for t in team_rows
                if _matches(q, t.team_name) or any(_matches(q, m.name, m.email) for m in t.members)
            ]
        return PerformanceResponse(
            exams=[ExamInfo(id=x.id, title=x.title, event_id=x.event_id, total_marks=exam_totals.get(x.id, 0)) for x in exams],
            hackathons=list(hackathons.values()),
            students=shown,
            teams=team_rows,
            total_students=len(students),
        )

    # ------------------------------------------------------------------ pieces

    async def _registrations(self, organization_id, institution_id, event_id, only_student_ids):
        stmt = (
            select(EventRegistration, InstitutionStudent, InstitutionEvent, Institution)
            .join(InstitutionStudent, InstitutionStudent.id == EventRegistration.student_id)
            .join(InstitutionEvent, InstitutionEvent.id == EventRegistration.event_id)
            .join(Institution, Institution.id == InstitutionEvent.institution_id)
            .where(EventRegistration.organization_id == organization_id)
            .order_by(func.lower(InstitutionStudent.name), InstitutionStudent.email, InstitutionEvent.start_date)
        )
        if institution_id is not None:
            stmt = stmt.where(InstitutionEvent.institution_id == institution_id)
        if event_id is not None:
            stmt = stmt.where(InstitutionEvent.id == event_id)
        if only_student_ids is not None:
            stmt = stmt.where(InstitutionStudent.id.in_(only_student_ids))
        return [tuple(row) for row in (await self.db.execute(stmt)).all()]

    async def _exam_marks(self, event_ids):
        """The exams linked to these events, their total marks, and each attendee's marks keyed by (event, email)."""
        if not event_ids:
            return [], {}, {}
        exams = list(
            (
                await self.db.execute(
                    select(WorkshopExam)
                    .where(WorkshopExam.event_id.in_(event_ids), WorkshopExam.hackathon_id.is_(None))
                    .order_by(WorkshopExam.created_at)
                )
            )
            .scalars()
            .all()
        )
        if not exams:
            return [], {}, {}
        exam_ids = [x.id for x in exams]
        totals = {
            exam_id: int(total)
            for exam_id, total in (
                await self.db.execute(
                    select(WorkshopExamQuestion.exam_id, func.coalesce(func.sum(WorkshopExamQuestion.marks), 0))
                    .where(WorkshopExamQuestion.exam_id.in_(exam_ids))
                    .group_by(WorkshopExamQuestion.exam_id)
                )
            ).all()
        }
        by_id = {x.id: x for x in exams}
        marks: dict[tuple[uuid.UUID, str], list[ExamMark]] = {}
        attendees = (
            await self.db.execute(select(WorkshopExamAttendee).where(WorkshopExamAttendee.exam_id.in_(exam_ids)))
        ).scalars()
        sat: dict[tuple[uuid.UUID, str, uuid.UUID], ExamMark] = {}
        for a in attendees:
            exam = by_id[a.exam_id]
            attended = a.submitted_at is not None and a.score is not None and not a.certificate_only
            sat[(exam.event_id, (a.email or "").strip().lower(), exam.id)] = ExamMark(
                exam_id=exam.id,
                title=exam.title,
                attended=attended,
                score=a.score if attended else None,
                total_marks=(a.total_marks if a.total_marks is not None else totals.get(exam.id, 0)) if attended else None,
            )
        # every exam of the event is listed for every attendee, so "did not sit" is visible rather than missing
        for (event_id, email, exam_id), mark in sat.items():
            marks.setdefault((event_id, email), []).append(mark)
        for key, items in marks.items():
            have = {m.exam_id for m in items}
            for exam in exams:
                if exam.event_id == key[0] and exam.id not in have:
                    items.append(ExamMark(exam_id=exam.id, title=exam.title, attended=False))
            items.sort(key=lambda m: [x.id for x in exams].index(m.exam_id))
        return exams, totals, marks

    async def _hackathons(self, event_ids):
        if not event_ids:
            return {}, {}, {}
        rows = list(
            (await self.db.execute(select(Hackathon).where(Hackathon.event_id.in_(event_ids)).order_by(Hackathon.start_date)))
            .scalars()
            .all()
        )
        if not rows:
            return {}, {}, {}
        hackathon_ids = [h.id for h in rows]
        max_totals = dict(
            (
                await self.db.execute(
                    select(ProblemStatement.hackathon_id, func.coalesce(func.sum(ProblemStatement.marks), 0))
                    .where(ProblemStatement.hackathon_id.in_(hackathon_ids))
                    .group_by(ProblemStatement.hackathon_id)
                )
            ).all()
        )
        hackathons = {
            h.id: HackathonInfo(id=h.id, title=h.title, event_id=h.event_id, max_total=int(max_totals.get(h.id, 0)))
            for h in rows
        }
        team_rows = (await self.db.execute(select(Team).where(Team.hackathon_id.in_(hackathon_ids)))).scalars().all()
        team_ids = [t.id for t in team_rows]
        scores: dict[uuid.UUID, tuple[int, int]] = {}
        if team_ids:
            scores = {
                tid: (int(total or 0), int(count))
                for tid, total, count in (
                    await self.db.execute(
                        select(TaskSubmission.team_id, func.sum(TaskSubmission.score), func.count(TaskSubmission.id))
                        .where(TaskSubmission.team_id.in_(team_ids), TaskSubmission.score.is_not(None))
                        .group_by(TaskSubmission.team_id)
                    )
                ).all()
            }
        teams: dict[uuid.UUID, TeamRef] = {}
        for t in team_rows:
            total, count = scores.get(t.id, (0, 0))
            teams[t.id] = TeamRef(
                team_id=t.id,
                team_name=t.name,
                hackathon_id=t.hackathon_id,
                hackathon_title=hackathons[t.hackathon_id].title,
                score=total,
                max_total=hackathons[t.hackathon_id].max_total,
                rank=None,
                tasks_scored=count,
            )
        # ranks within each hackathon among teams that have a scored task; equal totals share a rank (1, 1, 3)
        for hackathon_id in hackathons:
            scored = sorted((t for t in teams.values() if t.hackathon_id == hackathon_id and t.tasks_scored > 0), key=lambda t: -t.score)
            previous_score, previous_rank = None, 0
            for position, t in enumerate(scored, start=1):
                t.rank = previous_rank if t.score == previous_score else position
                previous_score, previous_rank = t.score, t.rank
        members: dict[uuid.UUID, list[tuple[str, str | None]]] = {}
        if team_ids:
            for team_id, name, email in (
                await self.db.execute(
                    select(HackathonTeamMember.team_id, Student.full_name, Student.email)
                    .join(Student, Student.id == HackathonTeamMember.student_id)
                    .where(HackathonTeamMember.team_id.in_(team_ids))
                    .order_by(Student.full_name)
                )
            ).all():
                members.setdefault(team_id, []).append((name, (email or "").strip().lower() or None))
        return hackathons, teams, members

    def _team_rows(self, pool, hackathons, teams, team_members, by_event_email, students, selected_ids):
        event_info = {event.id: (event.name, institution.name) for _, _, event, institution in pool}
        rows: list[TeamPerformance] = []
        in_a_team: set[tuple[uuid.UUID, str]] = set()
        for team in teams.values():
            event_id = hackathons[team.hackathon_id].event_id
            if event_id not in event_info:
                continue
            members: list[TeamMember] = []
            for name, email in team_members.get(team.team_id, []):
                match = by_event_email.get((event_id, email)) if email else None
                if match is not None:
                    in_a_team.add((event_id, email))
                members.append(
                    TeamMember(
                        name=match.name if match else name,
                        email=email,
                        student_id=match.student_id if match else None,
                        exam_score=match.exam_score if match else None,
                        exam_total=match.exam_total if match else None,
                        individual_score=match.individual_score if match else None,
                        selected=bool(match and match.selected),
                    )
                )
            event_name, institution_name = event_info[event_id]
            rows.append(
                TeamPerformance(
                    team_id=team.team_id,
                    team_name=team.team_name,
                    hackathon_id=team.hackathon_id,
                    hackathon_title=team.hackathon_title,
                    event_id=event_id,
                    event_name=event_name,
                    institution_name=institution_name,
                    score=team.score,
                    max_total=team.max_total,
                    rank=team.rank,
                    tasks_scored=team.tasks_scored,
                    members=members,
                )
            )
        # registered students who are in no team, grouped per event so nobody is invisible in the team view
        loners: dict[uuid.UUID, list[StudentPerformance]] = {}
        for s in students:
            if (s.event_id, s.email) not in in_a_team and s.team is None:
                loners.setdefault(s.event_id, []).append(s)
        for event_id, group in loners.items():
            if not any(hackathons[h].event_id == event_id for h in hackathons):
                continue  # an event with no hackathon has no teams to show; its students are in the student view
            event_name, institution_name = event_info[event_id]
            rows.append(
                TeamPerformance(
                    team_id=None,
                    team_name=NO_TEAM,
                    hackathon_id=None,
                    hackathon_title=None,
                    event_id=event_id,
                    event_name=event_name,
                    institution_name=institution_name,
                    score=None,
                    max_total=None,
                    rank=None,
                    members=[
                        TeamMember(
                            name=s.name,
                            email=s.email,
                            student_id=s.student_id,
                            exam_score=s.exam_score,
                            exam_total=s.exam_total,
                            individual_score=s.individual_score,
                            selected=s.selected,
                        )
                        for s in group
                    ],
                )
            )
        rows.sort(key=lambda t: (t.team_id is None, t.rank is None, t.rank or 0, t.team_name.lower()))
        return rows
