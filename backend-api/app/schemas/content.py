from datetime import date, datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field, computed_field, field_validator

from app.models.content import ContentReviewStatus
from app.schemas.problem import ProblemSummary


class ContentAuthor(BaseModel):
    id: str
    nickname: str
    avatar_url: Optional[str]


class CollectionSummary(BaseModel):
    id: int
    slug: str
    title: str
    description: Optional[str]
    company: Optional[str]
    cover_url: Optional[str]
    problem_count: int
    solved_count: Optional[int] = None

    @computed_field
    @property
    def completion_rate(self) -> Optional[float]:
        if self.solved_count is None:
            return None
        if self.problem_count == 0:
            return 0.0
        return round(self.solved_count * 100 / self.problem_count, 2)


class CollectionPage(BaseModel):
    items: list[CollectionSummary]
    total: int
    page: int
    page_size: int
    pages: int


class CollectionProblemPublic(BaseModel):
    sequence: int
    problem: ProblemSummary


class CollectionDetail(CollectionSummary):
    problems: list[CollectionProblemPublic]
    page: int
    page_size: int
    pages: int


class CollectionCreate(BaseModel):
    slug: str = Field(min_length=1, max_length=100, pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
    title: str = Field(min_length=1, max_length=200)
    description: Optional[str] = Field(default=None, max_length=10_000)
    company: Optional[str] = Field(default=None, max_length=50)
    cover_url: Optional[str] = Field(default=None, max_length=2_000)
    problem_ids: list[int] = Field(default_factory=list, max_length=500)

    @field_validator("problem_ids")
    @classmethod
    def unique_problem_ids(cls, value: list[int]) -> list[int]:
        if len(value) != len(set(value)):
            raise ValueError("problem_ids must not contain duplicates")
        return value


class CollectionUpdate(BaseModel):
    slug: Optional[str] = Field(
        default=None,
        min_length=1,
        max_length=100,
        pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$",
    )
    title: Optional[str] = Field(default=None, min_length=1, max_length=200)
    description: Optional[str] = Field(default=None, max_length=10_000)
    company: Optional[str] = Field(default=None, max_length=50)
    cover_url: Optional[str] = Field(default=None, max_length=2_000)


class CollectionOrderUpdate(BaseModel):
    problem_ids: list[int] = Field(max_length=500)

    @field_validator("problem_ids")
    @classmethod
    def unique_problem_ids(cls, value: list[int]) -> list[int]:
        if len(value) != len(set(value)):
            raise ValueError("problem_ids must not contain duplicates")
        return value


class AdminCollection(CollectionDetail):
    is_public: bool


class AdminCollectionSummary(CollectionSummary):
    is_public: bool


class AdminCollectionPage(BaseModel):
    items: list[AdminCollectionSummary]
    total: int
    page: int
    page_size: int
    pages: int


class DailyChallengePublic(BaseModel):
    challenge_date: date
    timezone: str
    problem: ProblemSummary


class DailyChallengeSet(BaseModel):
    problem_id: int = Field(gt=0)


class DailyChallengeAdminItem(BaseModel):
    challenge_date: date
    timezone: str
    problem: ProblemSummary


class DailyChallengeAdminPage(BaseModel):
    items: list[DailyChallengeAdminItem]
    total: int
    page: int
    page_size: int
    pages: int


class DiscussionCreate(BaseModel):
    title: str = Field(min_length=2, max_length=200)
    content: str = Field(min_length=2, max_length=50_000)


class DiscussionUpdate(BaseModel):
    title: Optional[str] = Field(default=None, min_length=2, max_length=200)
    content: Optional[str] = Field(default=None, min_length=2, max_length=50_000)


class DiscussionPublic(BaseModel):
    id: int
    problem_id: int
    author: Optional[ContentAuthor]
    title: str
    content: str
    is_pinned: bool
    is_locked: bool
    comment_count: int
    review_status: ContentReviewStatus
    created_at: datetime
    updated_at: datetime
    can_edit: bool = False


class DiscussionPage(BaseModel):
    items: list[DiscussionPublic]
    total: int
    page: int
    page_size: int
    pages: int


class CommentCreate(BaseModel):
    content: str = Field(min_length=1, max_length=20_000)
    parent_id: Optional[int] = Field(default=None, gt=0)


class CommentUpdate(BaseModel):
    content: str = Field(min_length=1, max_length=20_000)


class CommentPublic(BaseModel):
    id: int
    discussion_id: int
    parent_id: Optional[int]
    depth: int
    author: Optional[ContentAuthor]
    content: str
    deleted: bool
    review_status: ContentReviewStatus
    created_at: datetime
    updated_at: datetime
    can_edit: bool = False


class CommentPage(BaseModel):
    items: list[CommentPublic]
    total: int
    page: int
    page_size: int
    pages: int


class DiscussionDetail(BaseModel):
    discussion: DiscussionPublic
    comments: CommentPage


class ReportCreate(BaseModel):
    reason: str = Field(min_length=2, max_length=500)


class ReportState(BaseModel):
    report_id: int
    created: bool


class ModerationUpdate(BaseModel):
    review_status: ContentReviewStatus
    reason: Optional[str] = Field(default=None, max_length=500)


class DiscussionAdminUpdate(BaseModel):
    is_pinned: Optional[bool] = None
    is_locked: Optional[bool] = None


class ReportAdminUpdate(BaseModel):
    status: Literal["resolved", "dismissed"]
    reason: Optional[str] = Field(default=None, max_length=500)


class ContentReportPublic(BaseModel):
    id: int
    reporter_id: Optional[str]
    discussion_id: Optional[int]
    comment_id: Optional[int]
    reason: str
    status: str
    created_at: datetime


class ContentReportPage(BaseModel):
    items: list[ContentReportPublic]
    total: int
    page: int
    page_size: int
    pages: int


class ModerationQueueItem(BaseModel):
    target_type: Literal["discussion", "comment"]
    target_id: int
    discussion_id: int
    problem_id: int
    author: Optional[ContentAuthor]
    title: Optional[str]
    content: str
    review_status: ContentReviewStatus
    is_pinned: bool = False
    is_locked: bool = False
    created_at: datetime


class ModerationQueuePage(BaseModel):
    items: list[ModerationQueueItem]
    total: int
    page: int
    page_size: int
    pages: int
