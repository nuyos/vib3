from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Dict

from .repository import todo_repo, user_repo
from .services import normalize_due_date, todo_service


def _ensure_user(name: str, role: str) -> tuple[int, bool]:
    existing = user_repo.find_by_name(name)
    if existing is not None:
        return existing.id, False
    user = user_repo.create(name, role)
    return user.id, True


def seed_example_data() -> Dict[str, int]:
    """Insert example teachers, students, and todos if they do not already exist."""
    created_users = 0
    created_todos = 0

    teacher_id, teacher_created = _ensure_user("담임 선생님", "teacher")
    if teacher_created:
        created_users += 1

    student_names = ["홍길동", "김민수", "이서연"]
    student_ids = []
    for name in student_names:
        student_id, created = _ensure_user(name, "student")
        if created:
            created_users += 1
        student_ids.append(student_id)

    today = date.today()
    todo_specs = [
        ("수학 숙제", "교재 32쪽 문제 풀기", student_ids[0], False, today.isoformat()),
        ("과학 보고서", "태양계 자료 조사", student_ids[1], False, (today + timedelta(days=2)).isoformat()),
        (
            "국어 일기",
            "주말 활동 일기 작성",
            student_ids[2],
            True,
            (today + timedelta(days=1)).isoformat(),
            datetime.now().isoformat(timespec="seconds"),
        ),
    ]

    for spec in todo_specs:
        title, description, assignee_id, completed, due_date, *maybe_completed_at = spec
        existing = todo_repo.find_by_title_and_owner(title, teacher_id)
        if existing is None:
            completed_at = maybe_completed_at[0] if maybe_completed_at else None
            todo_service.create_todos(
                teacher_id,
                title=title,
                description=description,
                due_date=normalize_due_date(due_date),
                completed=completed,
                assignee_id=assignee_id,
                completed_at=completed_at if completed else None,
            )
            created_todos += 1

    return {"created_users": created_users, "created_todos": created_todos}
