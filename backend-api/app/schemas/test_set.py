from datetime import datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from app.models.problem import CheckerType, TestSetStatus


class TestSetIssue(BaseModel):
    code: str
    message: str
    sequence: Optional[int] = None


class TestSetCreate(BaseModel):
    checker_type: CheckerType = CheckerType.EXACT
    absolute_tolerance: Optional[Decimal] = Field(default=None, ge=0)
    relative_tolerance: Optional[Decimal] = Field(default=None, ge=0)

    @model_validator(mode="after")
    def validate_checker(self) -> "TestSetCreate":
        if self.checker_type is CheckerType.FLOAT:
            if self.absolute_tolerance is None or self.relative_tolerance is None:
                raise ValueError("float checker requires both tolerances")
            if self.absolute_tolerance == 0 and self.relative_tolerance == 0:
                raise ValueError("float checker requires a positive tolerance")
        elif self.absolute_tolerance is not None or self.relative_tolerance is not None:
            raise ValueError("exact and token checkers do not accept tolerances")
        return self


class TestCaseCreate(BaseModel):
    sequence: int = Field(ge=0)
    score: Decimal = Field(gt=0, le=100, decimal_places=2)
    input_object_key: str = Field(min_length=1, max_length=1024)
    output_object_key: str = Field(min_length=1, max_length=1024)
    checksum: str = Field(pattern=r"^[0-9a-f]{64}$")


class TestCaseAdminPublic(BaseModel):
    id: UUID
    sequence: int
    score: Decimal
    input_size_bytes: int
    output_size_bytes: int


class TestSetAdminPublic(BaseModel):
    id: UUID
    problem_id: int
    version: int
    status: TestSetStatus
    checker_type: CheckerType
    absolute_tolerance: Optional[Decimal]
    relative_tolerance: Optional[Decimal]
    case_count: int
    total_score: Decimal
    created_by: Optional[UUID]
    created_at: datetime
    activated_at: Optional[datetime]
    cases: list[TestCaseAdminPublic] = Field(default_factory=list)


class TestSetValidationPublic(BaseModel):
    test_set: TestSetAdminPublic
    issues: list[TestSetIssue]
