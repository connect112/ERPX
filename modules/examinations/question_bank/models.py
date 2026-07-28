import enum
import uuid

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_model import TimestampedBase
from modules.courses.models import Course  # noqa: F401
from modules.organizations.models import Organization  # noqa: F401


class QuestionType(str, enum.Enum):
    MCQ = "mcq"
    TRUE_FALSE = "true_false"
    SHORT_ANSWER = "short_answer"
    ESSAY = "essay"
    CODING = "coding"


class Difficulty(str, enum.Enum):
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"


def _values(enum_cls):
    return [m.value for m in enum_cls]


class Question(TimestampedBase):
    __tablename__ = "exam_questions_bank"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    course_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("courses.id", ondelete="SET NULL"), nullable=True, index=True
    )
    question_text: Mapped[str] = mapped_column(Text, nullable=False)
    question_type: Mapped[QuestionType] = mapped_column(
        SAEnum(QuestionType, name="question_type", values_callable=_values),
        default=QuestionType.MCQ,
        server_default=QuestionType.MCQ.value,
        nullable=False,
    )
    # For MCQ/TRUE_FALSE: list of option strings, e.g. ["A. ...", "B. ..."].
    options: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    # Auto-gradable answer key for MCQ/TRUE_FALSE/SHORT_ANSWER; null for
    # ESSAY/CODING, which are always manually graded via Evaluation.
    correct_answer: Mapped[str | None] = mapped_column(Text, nullable=True)
    default_marks: Mapped[int] = mapped_column(Integer, default=1, server_default="1", nullable=False)
    difficulty: Mapped[Difficulty] = mapped_column(
        SAEnum(Difficulty, name="question_difficulty", values_callable=_values),
        default=Difficulty.MEDIUM,
        server_default=Difficulty.MEDIUM.value,
        nullable=False,
    )
