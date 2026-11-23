import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from fastapi import UploadFile

from app.core.exceptions import NotFoundError, ValidationError
from app.core.logging_config import get_logger
from modules.courses.chapters.repository import ChapterRepository
from modules.courses.lessons.repository import LessonRepository
from modules.courses.repository import CourseRepository
from modules.courses.resources.models import Resource
from modules.courses.resources.repository import ResourceRepository
from packages.storage.client import get_storage_client

logger = get_logger(__name__)

MAX_UPLOAD_BYTES = 25 * 1024 * 1024
# programs that run on a student's machine are never handed round through the curriculum
BLOCKED_EXTENSIONS = {
    ".exe", ".msi", ".bat", ".cmd", ".com", ".scr", ".pif", ".vbs", ".vbe", ".js", ".jse", ".wsf", ".wsh",
    ".ps1", ".psm1", ".lnk", ".reg", ".dll", ".jar", ".hta", ".cpl", ".apk", ".sh", ".html", ".htm", ".svg",
}  # fmt: skip
# what a file's first bytes must look like for the kinds we can recognize
SIGNATURES = {
    ".pdf": (b"%PDF-",),
    ".png": (b"\x89PNG\r\n\x1a\n",),
    ".jpg": (b"\xff\xd8\xff",),
    ".jpeg": (b"\xff\xd8\xff",),
    ".gif": (b"GIF87a", b"GIF89a"),
    ".zip": (b"PK\x03\x04",),
    ".docx": (b"PK\x03\x04",),
    ".xlsx": (b"PK\x03\x04",),
    ".pptx": (b"PK\x03\x04",),
}


def safe_filename(name: str) -> str:
    import os
    import re

    base = os.path.basename((name or "").replace("\\", "/")).strip()
    base = re.sub(r"[^A-Za-z0-9._ \-()]", "_", base).strip(" .")
    return (base or "file")[:150]


class ResourceService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = ResourceRepository(db)
        self.lesson_repo = LessonRepository(db)
        self.chapter_repo = ChapterRepository(db)
        self.course_repo = CourseRepository(db)

    async def _get_owned_lesson(
        self,
        lesson_id: uuid.UUID,
        chapter_id: uuid.UUID,
        course_id: uuid.UUID,
        organization_id: uuid.UUID,
    ):
        course = await self.course_repo.get_by_id(course_id, organization_id)
        if not course:
            raise NotFoundError("Course", course_id)
        chapter = await self.chapter_repo.get_by_id(chapter_id)
        if not chapter or chapter.course_id != course_id:
            raise NotFoundError("Chapter", chapter_id)
        lesson = await self.lesson_repo.get_by_id(lesson_id)
        if not lesson or lesson.chapter_id != chapter_id:
            raise NotFoundError("Lesson", lesson_id)
        return lesson

    async def create_resource(
        self,
        lesson_id: uuid.UUID,
        chapter_id: uuid.UUID,
        course_id: uuid.UUID,
        organization_id: uuid.UUID,
        **fields,
    ) -> Resource:
        await self._get_owned_lesson(lesson_id, chapter_id, course_id, organization_id)
        resource = await self.repo.create(lesson_id=lesson_id, **fields)
        logger.info("resource_created", resource_id=str(resource.id), lesson_id=str(lesson_id))
        return resource

    async def list_resources(
        self,
        lesson_id: uuid.UUID,
        chapter_id: uuid.UUID,
        course_id: uuid.UUID,
        organization_id: uuid.UUID,
    ) -> list[Resource]:
        await self._get_owned_lesson(lesson_id, chapter_id, course_id, organization_id)
        return await self.repo.list_for_lesson(lesson_id)

    async def get_resource(
        self,
        resource_id: uuid.UUID,
        lesson_id: uuid.UUID,
        chapter_id: uuid.UUID,
        course_id: uuid.UUID,
        organization_id: uuid.UUID,
    ) -> Resource:
        await self._get_owned_lesson(lesson_id, chapter_id, course_id, organization_id)
        resource = await self.repo.get_by_id(resource_id)
        if not resource or resource.lesson_id != lesson_id:
            raise NotFoundError("Resource", resource_id)
        return resource

    async def update_resource(
        self,
        resource_id: uuid.UUID,
        lesson_id: uuid.UUID,
        chapter_id: uuid.UUID,
        course_id: uuid.UUID,
        organization_id: uuid.UUID,
        **fields,
    ) -> Resource:
        resource = await self.get_resource(
            resource_id, lesson_id, chapter_id, course_id, organization_id
        )
        if resource.storage_key is not None and "file_url" in fields:
            raise ValidationError("An uploaded file's address cannot be changed. Delete it and upload the new file.")
        updated = await self.repo.update(resource, **fields)
        logger.info("resource_updated", resource_id=str(resource_id))
        return updated

    async def delete_resource(
        self,
        resource_id: uuid.UUID,
        lesson_id: uuid.UUID,
        chapter_id: uuid.UUID,
        course_id: uuid.UUID,
        organization_id: uuid.UUID,
    ) -> None:
        resource = await self.get_resource(
            resource_id, lesson_id, chapter_id, course_id, organization_id
        )
        key = resource.storage_key
        await self.repo.delete(resource)
        if key:
            await self._forget_object(key)  # the record goes first: the file is removed best-effort
        logger.info("resource_deleted", resource_id=str(resource_id))

    # ------------------------------------------------------------------ uploaded files

    async def create_upload(
        self,
        lesson_id: uuid.UUID,
        chapter_id: uuid.UUID,
        course_id: uuid.UUID,
        organization_id: uuid.UUID,
        *,
        upload: UploadFile,
        title: str,
        resource_type,
        is_downloadable: bool,
        user_id: uuid.UUID | None,
    ) -> Resource:
        """Store an uploaded file as a lesson resource. Checked before anything is kept: a name that cannot be a program or a page, a size
        limit, and (for the kinds we can recognize) that the bytes really are what the extension says."""
        import os

        await self._get_owned_lesson(lesson_id, chapter_id, course_id, organization_id)
        filename = safe_filename(upload.filename or "")
        extension = os.path.splitext(filename)[1].lower()
        if extension in BLOCKED_EXTENSIONS:
            raise ValidationError(f"{filename}: this type of file cannot be uploaded.")
        data = await upload.read(MAX_UPLOAD_BYTES + 1)
        if not data:
            raise ValidationError(f"{filename} is empty.")
        if len(data) > MAX_UPLOAD_BYTES:
            raise ValidationError(f"{filename} is larger than {MAX_UPLOAD_BYTES // (1024 * 1024)} MB.")
        signatures = SIGNATURES.get(extension)
        if signatures and not data.startswith(signatures):
            raise ValidationError(f"{filename} is not a valid {extension.lstrip('.').upper()} file.")
        if getattr(resource_type, "value", resource_type) == "pdf" and extension != ".pdf":
            raise ValidationError("A PDF resource must be a .pdf file.")
        content_type = (upload.content_type or "application/octet-stream")[:150]
        storage = get_storage_client()
        await storage.ensure_bucket()
        key = f"courses/{organization_id}/{course_id}/lessons/{lesson_id}/{uuid.uuid4().hex}-{filename}"
        await storage.upload_bytes(key, data, content_type)
        try:
            resource = await self.repo.create(
                lesson_id=lesson_id,
                title=title,
                resource_type=resource_type,
                file_url="pending",
                is_downloadable=is_downloadable,
                storage_key=key,
                original_filename=filename,
                content_type=content_type,
                size_bytes=len(data),
                uploaded_by_user_id=user_id,
            )
            resource.file_url = f"/api/v1/courses/{course_id}/chapters/{chapter_id}/lessons/{lesson_id}/resources/{resource.id}/download"
            await self.db.flush()
        except Exception:
            await self._forget_object(key)  # nothing kept in storage without a record
            raise
        logger.info("resource_uploaded", resource_id=str(resource.id), lesson_id=str(lesson_id), size=len(data))
        return resource

    async def download_link(self, resource: Resource) -> tuple[str, str]:
        if resource.storage_key is None:
            raise ValidationError("This resource is a link, not an uploaded file.")
        storage = get_storage_client()
        return storage.presigned_download_url(resource.storage_key), resource.original_filename or "file"

    @staticmethod
    async def _forget_object(key: str) -> None:
        try:
            await get_storage_client().delete_object(key)
        except Exception:  # noqa: BLE001 - a leftover object is harmless, a failed cleanup must not hide the real error
            logger.warning("resource_object_delete_failed", object_key=key, exc_info=True)
