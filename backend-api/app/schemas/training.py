from datetime import datetime

from pydantic import BaseModel

from app.models.problem import ProblemDifficulty
from app.schemas.problem import ProblemPage, TagPublic
from app.schemas.submission import SubmissionPublic


class FavoriteState(BaseModel):
    problem_id: int
    favorited: bool


class SolvedProblemPublic(BaseModel):
    id: int
    slug: str
    title: str
    difficulty: ProblemDifficulty
    attempt_count: int
    first_accepted_at: datetime


class DifficultyTrainingStat(BaseModel):
    difficulty: ProblemDifficulty
    total_count: int
    attempted_count: int
    solved_count: int


class TagTrainingStat(BaseModel):
    tag: TagPublic
    total_count: int
    attempted_count: int
    solved_count: int


class TrainingCounters(BaseModel):
    solved_count: int
    submission_count: int
    accepted_count: int


class TrainingDashboard(BaseModel):
    counters: TrainingCounters
    recent_submissions: list[SubmissionPublic]
    solved_problems: list[SolvedProblemPublic]
    difficulty_stats: list[DifficultyTrainingStat]
    tag_stats: list[TagTrainingStat]


class FavoriteProblemPage(ProblemPage):
    pass
