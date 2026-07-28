import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.core.logging_config import get_logger
from modules.pentrix.lab_instances.models import LabInstance, LabInstanceStatus
from modules.pentrix.lab_instances.provisioning import get_provisioner
from modules.pentrix.lab_instances.repository import LabInstanceRepository
from modules.pentrix.labs.repository import LabRepository
from modules.students.repository import StudentRepository

logger = get_logger(__name__)


class LabInstanceService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = LabInstanceRepository(db)
        self.lab_repo = LabRepository(db)
        self.student_repo = StudentRepository(db)
        self.provisioner = get_provisioner()

    async def launch(
        self, lab_id: uuid.UUID, organization_id: uuid.UUID, student_id: uuid.UUID
    ) -> LabInstance:
        lab = await self.lab_repo.get_by_id(lab_id, organization_id)
        if not lab:
            raise NotFoundError("Lab", lab_id)
        if not lab.is_active:
            raise ValidationError("This lab is not currently active.")

        student = await self.student_repo.get_by_id(student_id, organization_id)
        if not student:
            raise NotFoundError("Student", student_id)

        existing = await self.repo.get_active_for_student_lab(student_id, lab_id)
        if existing:
            raise ConflictError("This student already has an active instance of this lab.")

        now = datetime.now(timezone.utc)
        instance = await self.repo.create(
            lab_id=lab_id,
            student_id=student_id,
            started_at=now,
            expires_at=now + timedelta(minutes=lab.default_duration_minutes),
        )

        try:
            provisioned = await self.provisioner.provision(lab_id, lab.environment_image)
        except Exception:
            logger.exception("lab_provisioning_failed", instance_id=str(instance.id))
            await self.repo.mark_failed(instance)
            raise ValidationError(
                "Failed to provision the lab environment. Please try again shortly."
            )

        running = await self.repo.mark_running(
            instance, provisioned.environment_ref, provisioned.access_endpoint
        )
        logger.info("lab_instance_launched", instance_id=str(instance.id), lab_id=str(lab_id))
        return running

    async def get_instance(self, instance_id: uuid.UUID, organization_id: uuid.UUID) -> LabInstance:
        instance = await self.repo.get_by_id(instance_id)
        if not instance:
            raise NotFoundError("Lab instance", instance_id)
        lab = await self.lab_repo.get_by_id(instance.lab_id, organization_id)
        if not lab:
            raise NotFoundError("Lab instance", instance_id)
        return instance

    async def list_for_student(self, student_id: uuid.UUID, organization_id: uuid.UUID) -> list[LabInstance]:
        student = await self.student_repo.get_by_id(student_id, organization_id)
        if not student:
            raise NotFoundError("Student", student_id)
        return await self.repo.list_for_student(student_id)

    async def stop(self, instance_id: uuid.UUID, organization_id: uuid.UUID) -> LabInstance:
        instance = await self.get_instance(instance_id, organization_id)
        if instance.status not in (LabInstanceStatus.RUNNING, LabInstanceStatus.PROVISIONING):
            raise ValidationError(
                f"This lab instance is already '{instance.status.value}' and cannot be stopped."
            )

        if instance.environment_ref:
            await self.provisioner.terminate(instance.environment_ref)

        stopped = await self.repo.stop(instance)
        logger.info("lab_instance_stopped", instance_id=str(instance_id))
        return stopped
