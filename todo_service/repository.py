from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Optional

from . import db


@dataclass
class User:
    id: int
    name: str
    role: str  # "teacher" or "student"

    def to_dict(self):
        return {"id": self.id, "name": self.name, "role": self.role}


class UserRepository:
    def create(self, name: str, role: str) -> User:
        conn = db.get_connection()
        cursor = conn.execute(
            "INSERT INTO users (name, role) VALUES (?, ?)",
            (name, role),
        )
        conn.commit()
        return User(id=cursor.lastrowid, name=name, role=role)

    def get(self, user_id: int) -> Optional[User]:
        row = db.get_connection().execute(
            "SELECT id, name, role FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()
        if row is None:
            return None
        return User(id=row["id"], name=row["name"], role=row["role"])

    def find_by_name(self, name: str) -> Optional[User]:
        row = db.get_connection().execute(
            "SELECT id, name, role FROM users WHERE name = ?",
            (name,),
        ).fetchone()
        if row is None:
            return None
        return User(id=row["id"], name=row["name"], role=row["role"])

    def list(self) -> Iterable[User]:
        rows = db.get_connection().execute(
            "SELECT id, name, role FROM users ORDER BY id"
        ).fetchall()
        return [User(id=row["id"], name=row["name"], role=row["role"]) for row in rows]

    def count(self) -> int:
        (count,) = db.get_connection().execute("SELECT COUNT(*) FROM users").fetchone()
        return int(count)

    def delete(self, user_id: int) -> bool:
        conn = db.get_connection()
        cursor = conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
        conn.commit()
        return cursor.rowcount > 0


@dataclass
class Todo:
    id: int
    title: str
    description: str
    completed: bool
    owner_id: int
    assignee_id: Optional[int]
    due_date: Optional[str]
    completed_at: Optional[str]

    def to_dict(self):
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "completed": self.completed,
            "owner_id": self.owner_id,
            "assignee_id": self.assignee_id,
            "due_date": self.due_date,
            "completed_at": self.completed_at,
        }


NO_UPDATE = object()


class TodoRepository:
    def _row_to_todo(self, row) -> Todo:
        return Todo(
            id=row["id"],
            title=row["title"],
            description=row["description"],
            completed=bool(row["completed"]),
            owner_id=row["owner_id"],
            assignee_id=row["assignee_id"],
            due_date=row["due_date"],
            completed_at=row["completed_at"],
        )

    def list(
        self,
        *,
        owner_id: Optional[int] = None,
        assignee_id: Optional[int] = None,
    ) -> Iterable[Todo]:
        query = (
            "SELECT id, title, description, completed, owner_id, assignee_id, due_date, completed_at "
            "FROM todos"
        )
        conditions = []
        params = []
        if owner_id is not None:
            conditions.append("owner_id = ?")
            params.append(owner_id)
        if assignee_id is not None:
            conditions.append("assignee_id = ?")
            params.append(assignee_id)
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        query += " ORDER BY id DESC"

        rows = db.get_connection().execute(query, params).fetchall()
        return [self._row_to_todo(row) for row in rows]

    def get(self, todo_id: int) -> Optional[Todo]:
        row = db.get_connection().execute(
            "SELECT id, title, description, completed, owner_id, assignee_id, due_date, completed_at "
            "FROM todos WHERE id = ?",
            (todo_id,),
        ).fetchone()
        if row is None:
            return None
        return self._row_to_todo(row)

    def find_by_title_and_owner(self, title: str, owner_id: int) -> Optional[Todo]:
        row = db.get_connection().execute(
            "SELECT id, title, description, completed, owner_id, assignee_id, due_date, completed_at "
            "FROM todos WHERE title = ? AND owner_id = ?",
            (title, owner_id),
        ).fetchone()
        if row is None:
            return None
        return self._row_to_todo(row)

    def create(
        self,
        *,
        title: str,
        description: str,
        completed: bool,
        owner_id: int,
        assignee_id: Optional[int],
        due_date: Optional[str],
        completed_at: Optional[str] = None,
    ) -> Todo:
        conn = db.get_connection()
        cursor = conn.execute(
            """
            INSERT INTO todos (title, description, completed, owner_id, assignee_id, due_date, completed_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (title, description, int(completed), owner_id, assignee_id, due_date, completed_at),
        )
        conn.commit()
        return self.get(cursor.lastrowid)

    def delete(self, todo_id: int) -> bool:
        conn = db.get_connection()
        cursor = conn.execute("DELETE FROM todos WHERE id = ?", (todo_id,))
        conn.commit()
        return cursor.rowcount > 0

    def update(
        self,
        todo_id: int,
        *,
        title: Optional[str] = None,
        description: Optional[str] = None,
        completed: Optional[bool] = None,
        assignee_id: object = NO_UPDATE,
        due_date: object = NO_UPDATE,
        completed_at: object = NO_UPDATE,
    ) -> Optional[Todo]:
        fields = []
        params = []
        if title is not None:
            fields.append("title = ?")
            params.append(title)
        if description is not None:
            fields.append("description = ?")
            params.append(description)
        if completed is not None:
            fields.append("completed = ?")
            params.append(int(completed))
        if assignee_id is not NO_UPDATE:
            fields.append("assignee_id = ?")
            params.append(assignee_id)
        if due_date is not NO_UPDATE:
            fields.append("due_date = ?")
            params.append(due_date)
        if completed_at is not NO_UPDATE:
            fields.append("completed_at = ?")
            params.append(completed_at)

        if not fields:
            return self.get(todo_id)

        params.append(todo_id)
        conn = db.get_connection()
        conn.execute(
            f"UPDATE todos SET {', '.join(fields)} WHERE id = ?",
            params,
        )
        conn.commit()
        return self.get(todo_id)

    def replace(
        self,
        todo_id: int,
        *,
        title: str,
        description: str,
        completed: bool,
        assignee_id: Optional[int],
        due_date: Optional[str],
        completed_at: Optional[str],
    ) -> Optional[Todo]:
        conn = db.get_connection()
        conn.execute(
            """
            UPDATE todos
            SET title = ?, description = ?, completed = ?, assignee_id = ?, due_date = ?, completed_at = ?
            WHERE id = ?
            """,
            (title, description, int(completed), assignee_id, due_date, completed_at, todo_id),
        )
        conn.commit()
        return self.get(todo_id)

    def count(self) -> int:
        (count,) = db.get_connection().execute("SELECT COUNT(*) FROM todos").fetchone()
        return int(count)


user_repo = UserRepository()
todo_repo = TodoRepository()
