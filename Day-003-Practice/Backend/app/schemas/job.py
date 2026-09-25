from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.enums import EmploymentType, JobStatus
from app.schemas.user import DepartmentOut, UserOut


class JobBase(BaseModel):
    title: str = Field(min_length=2, max_length=180)
    description: str | None = None
    location: str | None = None
    employment_type: EmploymentType = EmploymentType.FULL_TIME
    openings: int = Field(default=1, ge=1, le=999)
    experience_min: int | None = Field(default=None, ge=0, le=50)
    experience_max: int | None = Field(default=None, ge=0, le=50)
    salary_min: float | None = None
    salary_max: float | None = None
    skills: str | None = None
    target_close_date: date | None = None
    department_id: int | None = None
    hiring_manager_id: int | None = None
    recruiter_id: int | None = None


class JobCreate(JobBase):
    code: str | None = Field(default=None, max_length=30)
    status: JobStatus = JobStatus.DRAFT

    @field_validator("experience_max")
    @classmethod
    def check_experience(cls, v, info):
        low = info.data.get("experience_min")
        if v is not None and low is not None and v < low:
            raise ValueError("experience_max must be greater than or equal to experience_min")
        return v

    @field_validator("salary_max")
    @classmethod
    def check_salary(cls, v, info):
        low = info.data.get("salary_min")
        if v is not None and low is not None and v < low:
            raise ValueError("salary_max must be greater than or equal to salary_min")
        return v


class JobUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    location: str | None = None
    employment_type: EmploymentType | None = None
    status: JobStatus | None = None
    openings: int | None = Field(default=None, ge=1, le=999)
    experience_min: int | None = None
    experience_max: int | None = None
    salary_min: float | None = None
    salary_max: float | None = None
    skills: str | None = None
    target_close_date: date | None = None
    department_id: int | None = None
    hiring_manager_id: int | None = None
    recruiter_id: int | None = None


class JobOut(JobBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    code: str
    status: JobStatus
    created_at: datetime
    department: DepartmentOut | None = None
    hiring_manager: UserOut | None = None
    recruiter: UserOut | None = None
    applicant_count: int = 0
    hired_count: int = 0
