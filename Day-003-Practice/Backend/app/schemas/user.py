from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.core.enums import Role


class DepartmentBase(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    location: str | None = None


class DepartmentCreate(DepartmentBase):
    pass


class DepartmentOut(DepartmentBase):
    model_config = ConfigDict(from_attributes=True)
    id: int


class UserBase(BaseModel):
    email: EmailStr
    full_name: str = Field(min_length=2, max_length=150)
    role: Role = Role.RECRUITER
    title: str | None = None
    phone: str | None = None
    department_id: int | None = None


class UserCreate(UserBase):
    password: str = Field(min_length=8, max_length=128)


class UserUpdate(BaseModel):
    full_name: str | None = None
    role: Role | None = None
    title: str | None = None
    phone: str | None = None
    department_id: int | None = None
    is_active: bool | None = None


class UserOut(UserBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    is_active: bool
    created_at: datetime
    department: DepartmentOut | None = None
