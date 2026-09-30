import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class MessagePublic(BaseModel):
    id: uuid.UUID
    conversation_id: uuid.UUID
    sender_user_id: uuid.UUID | None
    body: str | None
    attachment_document_id: uuid.UUID | None
    read_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}


class ConversationPublic(BaseModel):
    id: uuid.UUID
    student_id: uuid.UUID
    trainer_id: uuid.UUID
    counterpart_name: str
    last_message: MessagePublic | None
    unread_count: int
    created_at: datetime


class ConversationListResponse(BaseModel):
    items: list[ConversationPublic]


class TrainerContactPublic(BaseModel):
    trainer_id: uuid.UUID
    full_name: str


class StudentContactPublic(BaseModel):
    student_id: uuid.UUID
    full_name: str


class OpenConversationResponse(BaseModel):
    id: uuid.UUID
    student_id: uuid.UUID
    trainer_id: uuid.UUID


class SendMessageRequest(BaseModel):
    body: str | None = Field(default=None, max_length=4000)
    attachment_document_id: uuid.UUID | None = None


class AttachmentUploadRequest(BaseModel):
    filename: str = Field(..., min_length=1, max_length=255)
    content_type: str = Field(..., min_length=1, max_length=255)


class AttachmentUploadResponse(BaseModel):
    document_id: uuid.UUID
    upload_url: str


class UnreadCountResponse(BaseModel):
    unread_count: int


class MessageResponse(BaseModel):
    message: str


# ---- admin oversight ----


class AdminConversationPublic(BaseModel):
    id: uuid.UUID
    student_id: uuid.UUID
    student_name: str
    trainer_id: uuid.UUID
    trainer_name: str
    last_message: MessagePublic | None
    created_at: datetime


class AdminConversationListResponse(BaseModel):
    items: list[AdminConversationPublic]
    total: int
    skip: int
    limit: int
