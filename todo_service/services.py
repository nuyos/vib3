from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Iterable, List, Optional

from . import db
from .repository import NO_UPDATE, Todo, todo_repo, user_repo


@dataclass
class ServiceError(RuntimeError):
    message: str

    def __str__(self) -> str:  # pragma: no cover - message passthrough
        return self.message


class NotFoundError(ServiceError):
    """Raised when an entity is not found."""


class PermissionDeniedError(ServiceError):
    """Raised when the caller is not allowed to perform the action."""


class ValidationError(ServiceError):
    """Raised when the input data is invalid."""


class UserService:
    def __init__(self, repo=user_repo) -> None:
        self._repo = repo

    def create_user(self, name: str, role: str):
        return self._repo.create(name, role)

    def create_student(self, name: str):
        return self._repo.create(name, "student")

    def list_users(self) -> Iterable:
        return self._repo.list()

    def list_students(self) -> List:
        return [user for user in self._repo.list() if user.role == "student"]

    def get_user(self, user_id: int):
        user = self._repo.get(user_id)
        if user is None:
            raise NotFoundError("사용자를 찾을 수 없습니다.")
        return user

    def ensure_teacher(self, user_id: int):
        user = self.get_user(user_id)
        if user.role != "teacher":
            raise PermissionDeniedError("선생님 권한이 필요합니다.")
        return user

    def ensure_student(self, user_id: int):
        user = self.get_user(user_id)
        if user.role != "student":
            raise ValidationError("올바른 학생 ID가 필요합니다.")
        return user

    def delete_student(self, student_id: int) -> None:
        student = self.ensure_student(student_id)
        self._repo.delete(student.id)


class TodoService:
    def __init__(self, repo=todo_repo, user_service: UserService = None) -> None:
        self._repo = repo
        self._users = user_service or UserService()

    def list_for_teacher(self, teacher_id: int) -> List[Todo]:
        self._users.ensure_teacher(teacher_id)
        return list(self._repo.list(owner_id=teacher_id))

    def list_for_student(self, student_id: int) -> List[Todo]:
        self._users.ensure_student(student_id)
        return list(self._repo.list(assignee_id=student_id))

    def create_todos(
        self,
        owner_id: int,
        *,
        title: str,
        description: str = "",
        due_date: Optional[str] = None,
        completed: bool = False,
        assignee_id: Optional[int] = None,
        completed_at: Optional[str] = None,
    ) -> List[Todo]:
        self._users.ensure_teacher(owner_id)
        created: List[Todo] = []

        if assignee_id is None:
            students = self._users.list_students()
            if not students:
                raise ValidationError("학생이 존재하지 않습니다.")
            for student in students:
                created.append(
                    self._repo.create(
                        title=title,
                        description=description,
                        completed=completed,
                        owner_id=owner_id,
                        assignee_id=student.id,
                        due_date=due_date,
                        completed_at=completed_at if completed_at is not None else _completion_timestamp(completed),
                    )
                )
        else:
            student = self._users.ensure_student(assignee_id)
            created.append(
                self._repo.create(
                    title=title,
                    description=description,
                    completed=completed,
                    owner_id=owner_id,
                    assignee_id=student.id,
                    due_date=due_date,
                    completed_at=completed_at if completed_at is not None else _completion_timestamp(completed),
                )
            )
        return created

    def _get_todo(self, todo_id: int) -> Todo:
        todo = self._repo.get(todo_id)
        if todo is None:
            raise NotFoundError("TODO 항목을 찾을 수 없습니다.")
        return todo

    def verify_teacher_access(self, todo_id: int, teacher_id: int) -> Todo:
        todo = self._get_todo(todo_id)
        if todo.owner_id != teacher_id:
            raise PermissionDeniedError("해당 TODO에 접근할 수 없습니다.")
        return todo

    def verify_student_access(self, todo_id: int, student_id: int) -> Todo:
        todo = self._get_todo(todo_id)
        if todo.assignee_id != student_id:
            raise PermissionDeniedError("해당 TODO에 접근할 수 없습니다.")
        return todo

    def assign_todo(self, todo_id: int, owner_id: int, student_id: int) -> Todo:
        self.verify_teacher_access(todo_id, owner_id)
        student = self._users.ensure_student(student_id)
        return self._repo.update(todo_id, assignee_id=student.id)

    def update_todo_by_teacher(
        self,
        todo_id: int,
        owner_id: int,
        *,
        title: Optional[str] = None,
        description: Optional[str] = None,
        due_date: object = NO_UPDATE,
        completed: Optional[bool] = None,
        assignee_id: object = NO_UPDATE,
    ) -> Todo:
        todo = self.verify_teacher_access(todo_id, owner_id)

        assignee_arg = NO_UPDATE
        if assignee_id is not NO_UPDATE:
            if assignee_id is None:
                assignee_arg = None
            else:
                assignee = self._users.ensure_student(assignee_id)
                assignee_arg = assignee.id

        completed_at_arg = NO_UPDATE
        if completed is not None and completed != todo.completed:
            completed_at_arg = completed_at if completed_at is not None else _completion_timestamp(completed)

        return self._repo.update(
            todo_id,
            title=title,
            description=description,
            completed=completed,
            assignee_id=assignee_arg,
            due_date=due_date,
            completed_at=completed_at_arg,
        )

    def update_todo_by_student(self, todo_id: int, student_id: int, completed: bool) -> Todo:
        self.verify_student_access(todo_id, student_id)
        return self._repo.update(
            todo_id,
            completed=completed,
            assignee_id=NO_UPDATE,
            due_date=NO_UPDATE,
            completed_at=_completion_timestamp(completed),
        )

    def delete_todo(self, todo_id: int, owner_id: int) -> None:
        self.verify_teacher_access(todo_id, owner_id)
        self._repo.delete(todo_id)


def _completion_timestamp(completed: bool) -> Optional[str]:
    return datetime.now().isoformat(timespec="seconds") if completed else None


def normalize_due_date(value: Optional[str]) -> Optional[str]:
    if value in (None, ""):
        return None
    if not isinstance(value, str):
        raise ValidationError("마감일은 YYYY-MM-DD 형식이어야 합니다.")
    try:
        parsed = date.fromisoformat(value)
    except ValueError as exc:
        raise ValidationError("마감일은 YYYY-MM-DD 형식이어야 합니다.") from exc
    return parsed.isoformat()


user_service = UserService()
todo_service = TodoService(user_service=user_service)
