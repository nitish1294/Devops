from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select

from app.api.deps import CurrentUser, Db, ManageUsers
from app.core.enums import Role
from app.core.security import hash_password
from app.models.department import Department
from app.models.user import User
from app.schemas.common import Message, Page
from app.schemas.user import (
    DepartmentCreate,
    DepartmentOut,
    UserCreate,
    UserOut,
    UserUpdate,
)
from app.services import activity

router = APIRouter(tags=["people"])


@router.get("/users", response_model=Page[UserOut])
async def list_users(
    db: Db,
    _: CurrentUser,
    q: str | None = None,
    role: Role | None = None,
    is_active: bool | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=200),
):
    stmt = select(User)
    if q:
        like = f"%{q.lower()}%"
        stmt = stmt.where(func.lower(User.full_name).like(like) | func.lower(User.email).like(like))
    if role:
        stmt = stmt.where(User.role == role)
    if is_active is not None:
        stmt = stmt.where(User.is_active.is_(is_active))

    total = (await db.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
    rows = (
        (
            await db.execute(
                stmt.order_by(User.full_name).offset((page - 1) * page_size).limit(page_size)
            )
        )
        .unique()
        .scalars()
        .all()
    )
    return Page[UserOut](
        items=[UserOut.model_validate(r) for r in rows],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post("/users", response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def create_user(payload: UserCreate, db: Db, actor: ManageUsers):
    exists = (
        await db.execute(select(User.id).where(User.email == payload.email.lower()))
    ).scalar_one_or_none()
    if exists:
        raise HTTPException(status.HTTP_409_CONFLICT, "A user with that email already exists")

    user = User(
        **payload.model_dump(exclude={"password", "email"}),
        email=payload.email.lower(),
        password_hash=hash_password(payload.password),
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    await activity.log(
        "user.create", "user", user.id, f"Added {user.full_name} as {user.role}", actor.id, actor.full_name
    )
    return user


@router.get("/users/{user_id}", response_model=UserOut)
async def get_user(user_id: int, db: Db, _: CurrentUser):
    user = (await db.execute(select(User).where(User.id == user_id))).unique().scalar_one_or_none()
    if not user:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
    return user


@router.patch("/users/{user_id}", response_model=UserOut)
async def update_user(
    user_id: int, payload: UserUpdate, db: Db, actor: ManageUsers
):
    user = (await db.execute(select(User).where(User.id == user_id))).unique().scalar_one_or_none()
    if not user:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(user, field, value)
    db.add(user)
    await db.commit()
    await db.refresh(user)
    await activity.log(
        "user.update", "user", user.id, f"Updated {user.full_name}", actor.id, actor.full_name
    )
    return user


@router.delete("/users/{user_id}", response_model=Message)
async def deactivate_user(user_id: int, db: Db, actor: ManageUsers):
    if user_id == actor.id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "You cannot deactivate your own account")
    user = (await db.execute(select(User).where(User.id == user_id))).unique().scalar_one_or_none()
    if not user:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
    user.is_active = False
    db.add(user)
    await db.commit()
    await activity.log(
        "user.deactivate", "user", user.id, f"Deactivated {user.full_name}", actor.id, actor.full_name
    )
    return Message(detail=f"{user.full_name} deactivated")


@router.get("/departments", response_model=list[DepartmentOut])
async def list_departments(db: Db, _: CurrentUser):
    rows = (await db.execute(select(Department).order_by(Department.name))).unique().scalars().all()
    return rows


@router.post("/departments", response_model=DepartmentOut, status_code=status.HTTP_201_CREATED)
async def create_department(
    payload: DepartmentCreate, db: Db, actor: ManageUsers
):
    dept = Department(**payload.model_dump())
    db.add(dept)
    await db.commit()
    await db.refresh(dept)
    await activity.log(
        "department.create", "department", dept.id, f"Created {dept.name}", actor.id, actor.full_name
    )
    return dept
