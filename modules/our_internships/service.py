import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, ValidationError
from modules.institutions.models import EventRegistration, Institution, InstitutionEvent, InstitutionStudent
from modules.our_internships.models import InternshipScope, InternshipSelection, OurInternship
from modules.our_internships.performance import PerformanceBuilder
from modules.our_internships.schemas import SelectedStudent


class OurInternshipService:
    def __init__(self, db: AsyncSession):
        self.db = db

    # ------------------------------------------------------------------ the internship

    async def get(self, internship_id: uuid.UUID, organization_id: uuid.UUID) -> OurInternship:
        internship = (
            await self.db.execute(
                select(OurInternship).where(OurInternship.id == internship_id, OurInternship.organization_id == organization_id)
            )
        ).scalar_one_or_none()
        if internship is None:
            raise NotFoundError("Internship", internship_id)
        return internship

    async def create(self, organization_id: uuid.UUID, user_id: uuid.UUID, **fields) -> OurInternship:
        institution_id, event_id = fields.get("institution_id"), fields.get("event_id")
        if institution_id is not None:
            institution = (
                await self.db.execute(
                    select(Institution.id).where(Institution.id == institution_id, Institution.organization_id == organization_id)
                )
            ).first()
            if institution is None:
                raise NotFoundError("Institution", institution_id)
        if event_id is not None:
            event = (
                await self.db.execute(
                    select(InstitutionEvent).where(
                        InstitutionEvent.id == event_id, InstitutionEvent.organization_id == organization_id
                    )
                )
            ).scalar_one_or_none()
            if event is None:
                raise NotFoundError("Event", event_id)
            if event.institution_id != institution_id:
                raise ValidationError("That event belongs to a different institution.")
        internship = OurInternship(organization_id=organization_id, created_by_user_id=user_id, **fields)
        self.db.add(internship)
        await self.db.flush()
        await self.db.refresh(internship)
        return internship

    async def update(self, internship: OurInternship, fields: dict) -> OurInternship:
        for key in ("title", "status"):
            if key in fields and fields[key] is None:
                raise ValidationError(f"{key.capitalize()} cannot be empty.")
        for key, value in fields.items():
            setattr(internship, key, value)
        await self.db.flush()
        return internship

    async def delete(self, internship: OurInternship) -> None:
        await self.db.delete(internship)
        await self.db.flush()

    async def list_all(self, organization_id: uuid.UUID) -> list[OurInternship]:
        return list(
            (
                await self.db.execute(
                    select(OurInternship)
                    .where(OurInternship.organization_id == organization_id)
                    .order_by(OurInternship.created_at.desc())
                )
            )
            .scalars()
            .all()
        )

    async def names(self, internships: list[OurInternship]) -> tuple[dict, dict, dict]:
        """institution names, event names and selected counts for a batch of internships."""
        institution_ids = {i.institution_id for i in internships if i.institution_id}
        event_ids = {i.event_id for i in internships if i.event_id}
        institutions = {}
        if institution_ids:
            institutions = dict((await self.db.execute(select(Institution.id, Institution.name).where(Institution.id.in_(institution_ids)))).all())
        events = {}
        if event_ids:
            events = dict((await self.db.execute(select(InstitutionEvent.id, InstitutionEvent.name).where(InstitutionEvent.id.in_(event_ids)))).all())
        counts = {}
        ids = [i.id for i in internships]
        if ids:
            counts = dict(
                (
                    await self.db.execute(
                        select(InternshipSelection.internship_id, func.count())
                        .where(InternshipSelection.internship_id.in_(ids))
                        .group_by(InternshipSelection.internship_id)
                    )
                ).all()
            )
        return institutions, events, counts

    # ------------------------------------------------------------------ what it may select from

    @staticmethod
    def scope_filters(
        internship: OurInternship, institution_id: uuid.UUID | None, event_id: uuid.UUID | None
    ) -> tuple[uuid.UUID | None, uuid.UUID | None]:
        """The pool is the internship's own scope; a viewer may narrow it further but never widen it."""
        if internship.scope == InternshipScope.INSTITUTION:
            institution_id = internship.institution_id
            if internship.event_id is not None:
                event_id = internship.event_id
        return institution_id, event_id

    async def selected_ids(self, internship_id: uuid.UUID) -> set[uuid.UUID]:
        return {
            sid
            for (sid,) in (
                await self.db.execute(select(InternshipSelection.student_id).where(InternshipSelection.internship_id == internship_id))
            ).all()
        }

    async def performance(
        self,
        internship: OurInternship,
        institution_id: uuid.UUID | None,
        event_id: uuid.UUID | None,
        q: str | None,
    ):
        institution_id, event_id = self.scope_filters(internship, institution_id, event_id)
        return await PerformanceBuilder(self.db).build(
            internship.organization_id,
            institution_id=institution_id,
            event_id=event_id,
            q=q,
            selected_ids=await self.selected_ids(internship.id),
        )

    # ------------------------------------------------------------------ the shortlist

    async def select(
        self, internship: OurInternship, student_ids: list[uuid.UUID], user_id: uuid.UUID, note: str | None
    ) -> tuple[int, int]:
        """Add students to the shortlist. Returns (added, already selected). Only students registered for an event in
        the internship's scope can be chosen."""
        wanted = list(dict.fromkeys(student_ids))
        institution_id, event_id = self.scope_filters(internship, None, None)
        eligible_query = (
            select(EventRegistration.student_id)
            .join(InstitutionEvent, InstitutionEvent.id == EventRegistration.event_id)
            .where(EventRegistration.organization_id == internship.organization_id, EventRegistration.student_id.in_(wanted))
        )
        if institution_id is not None:
            eligible_query = eligible_query.where(InstitutionEvent.institution_id == institution_id)
        if event_id is not None:
            eligible_query = eligible_query.where(InstitutionEvent.id == event_id)
        eligible = {sid for (sid,) in (await self.db.execute(eligible_query)).all()}
        if eligible != set(wanted):
            raise ValidationError("Only students registered for this internship's institution or event can be selected.")
        already = await self.selected_ids(internship.id)
        fresh = [sid for sid in wanted if sid not in already]
        for sid in fresh:
            self.db.add(
                InternshipSelection(
                    organization_id=internship.organization_id,
                    internship_id=internship.id,
                    student_id=sid,
                    selected_by_user_id=user_id,
                    note=note,
                )
            )
        await self.db.flush()
        return len(fresh), len(wanted) - len(fresh)

    async def unselect(self, internship: OurInternship, student_id: uuid.UUID) -> None:
        selection = (
            await self.db.execute(
                select(InternshipSelection).where(
                    InternshipSelection.internship_id == internship.id, InternshipSelection.student_id == student_id
                )
            )
        ).scalar_one_or_none()
        if selection is None:
            raise NotFoundError("Selected student", student_id)
        await self.db.delete(selection)
        await self.db.flush()

    async def set_note(self, internship: OurInternship, student_id: uuid.UUID, note: str | None) -> None:
        selection = (
            await self.db.execute(
                select(InternshipSelection).where(
                    InternshipSelection.internship_id == internship.id, InternshipSelection.student_id == student_id
                )
            )
        ).scalar_one_or_none()
        if selection is None:
            raise NotFoundError("Selected student", student_id)
        selection.note = note
        await self.db.flush()

    async def selected(self, internship: OurInternship) -> list[SelectedStudent]:
        rows = (
            await self.db.execute(
                select(InternshipSelection, InstitutionStudent, Institution)
                .join(InstitutionStudent, InstitutionStudent.id == InternshipSelection.student_id)
                .join(Institution, Institution.id == InstitutionStudent.institution_id)
                .where(InternshipSelection.internship_id == internship.id)
                .order_by(InternshipSelection.created_at)
            )
        ).all()
        if not rows:
            return []
        ids = {student.id for _, student, _ in rows}
        institution_id, event_id = self.scope_filters(internship, None, None)
        board = await PerformanceBuilder(self.db).build(
            internship.organization_id,
            institution_id=institution_id,
            event_id=event_id,
            only_student_ids=ids,
            selected_ids=ids,
            include_teams=True,
        )
        standings: dict[uuid.UUID, list] = {}
        for s in board.students:
            standings.setdefault(s.student_id, []).append(s)
        return [
            SelectedStudent(
                student_id=student.id,
                name=student.name,
                email=student.email,
                phone=student.phone,
                institution_id=institution.id,
                institution_name=institution.name,
                note=selection.note,
                selected_at=selection.created_at,
                offer_reference=selection.offer_reference,
                offer_status=selection.offer_status,
                offer_sent_at=selection.offer_sent_at,
                offer_error=selection.offer_error,
                standings=standings.get(student.id, []),
            )
            for selection, student, institution in rows
        ]
