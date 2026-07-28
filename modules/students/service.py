import uuid
from datetime import date

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.core.logging_config import get_logger
from modules.crm.admissions.models import AdmissionStatus
from modules.crm.admissions.repository import AdmissionRepository
from modules.crm.leads.repository import LeadRepository
from modules.students.models import Student, StudentStatus
from modules.students.repository import StudentRepository

logger = get_logger(__name__)


class StudentService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = StudentRepository(db)
        self.admission_repo = AdmissionRepository(db)
        self.lead_repo = LeadRepository(db)

    async def create_student(self, organization_id: uuid.UUID, **fields) -> Student:
        student = await self.repo.create(organization_id, **fields)
        logger.info("student_created", student_id=str(student.id), org_id=str(organization_id))
        return student

    async def create_from_admission(
        self,
        admission_id: uuid.UUID,
        organization_id: uuid.UUID,
        branch_id: uuid.UUID | None,
        enrollment_date: date | None,
    ) -> Student:
        admission = await self.admission_repo.get_by_id(admission_id, organization_id)
        if not admission:
            raise NotFoundError("Admission", admission_id)

        if admission.status != AdmissionStatus.CONFIRMED:
            raise ValidationError(
                "Only a CONFIRMED admission can be converted into a student. "
                f"This admission is currently '{admission.status.value}'."
            )

        existing = await self.repo.get_by_admission_id(admission_id)
        if existing:
            raise ConflictError("A student record already exists for this admission.")

        # Copy the lead's contact details across so the operator doesn't
        # have to re-type name/email/phone that's already on file.
        lead = await self.lead_repo.get_by_id(admission.lead_id, organization_id)
        if not lead:
            raise NotFoundError("Lead", admission.lead_id)

        student = await self.repo.create(
            organization_id=organization_id,
            admission_id=admission_id,
            branch_id=branch_id or admission.branch_id,
            full_name=lead.full_name,
            email=lead.email,
            phone=lead.phone,
            course_name=admission.course_name,
            batch_name=admission.batch_name,
            enrollment_date=enrollment_date or date.today(),
        )
        logger.info(
            "student_created_from_admission", student_id=str(student.id), admission_id=str(admission_id)
        )
        return student

    async def get_student(self, student_id: uuid.UUID, organization_id: uuid.UUID) -> Student:
        student = await self.repo.get_by_id(student_id, organization_id)
        if not student:
            raise NotFoundError("Student", student_id)
        return student

    async def list_students(self, organization_id: uuid.UUID, **filters) -> tuple[list[Student], int]:
        return await self.repo.list_for_organization(organization_id, **filters)

    async def update_student(
        self, student_id: uuid.UUID, organization_id: uuid.UUID, **fields
    ) -> Student:
        student = await self.get_student(student_id, organization_id)
        updated = await self.repo.update(student, **fields)
        logger.info("student_updated", student_id=str(student_id))
        return updated

    async def change_status(
        self,
        student_id: uuid.UUID,
        organization_id: uuid.UUID,
        status: StudentStatus,
        notes: str | None = None,
    ) -> Student:
        student = await self.get_student(student_id, organization_id)
        updated = await self.repo.set_status(student, status, notes)
        logger.info("student_status_changed", student_id=str(student_id), status=status.value)
        return updated

    async def delete_student(self, student_id: uuid.UUID, organization_id: uuid.UUID) -> None:
        student = await self.get_student(student_id, organization_id)
        await self.repo.soft_delete(student)
        logger.info("student_deleted", student_id=str(student_id))
