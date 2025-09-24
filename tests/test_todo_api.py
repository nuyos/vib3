from __future__ import annotations

import sys
from pathlib import Path
from typing import Dict, Generator

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import app
from todo_service import db
from todo_service.repository import todo_repo, user_repo
from todo_service.seed import seed_example_data


@pytest.fixture(autouse=True)
def setup_database() -> Generator[None, None, None]:
    db.configure(":memory:")
    db.init_schema()
    yield
    db.close_connection()


@pytest.fixture()
def client():
    app.config.update(TESTING=True)
    with app.test_client() as client:
        yield client


@pytest.fixture()
def users() -> Dict[str, int]:
    teacher = user_repo.create("Teacher", "teacher")
    student = user_repo.create("Student", "student")
    return {"teacher": teacher.id, "student": student.id}


def _headers(user_id: int) -> Dict[str, str]:
    return {"X-User-Id": str(user_id)}


def _create_todo(client, users, **payload):
    body = {"title": "Homework", **payload}
    if "assignee_id" not in body:
        body["assignee_id"] = users["student"]
    response = client.post(
        "/api/todos",
        json=body,
        headers=_headers(users["teacher"]),
    )
    assert response.status_code == 201
    return response.get_json()


def test_seed_example_data_is_idempotent():
    first = seed_example_data()
    assert first["created_users"] >= 4
    assert first["created_todos"] >= 3

    second = seed_example_data()
    assert second == {"created_users": 0, "created_todos": 0}


def test_list_initially_empty_for_teacher(client, users):
    response = client.get("/api/todos", headers=_headers(users["teacher"]))
    assert response.status_code == 200
    assert response.get_json() == []


def test_student_cannot_create(client, users):
    response = client.post(
        "/api/todos",
        json={"title": "Homework"},
        headers=_headers(users["student"]),
    )
    assert response.status_code == 403


def test_teacher_create_and_both_can_view(client, users):
    created = _create_todo(client, users, assignee_id=users["student"])
    todo_id = created["id"]

    teacher_view = client.get(f"/api/todos/{todo_id}", headers=_headers(users["teacher"]))
    assert teacher_view.status_code == 200

    student_view = client.get(f"/api/todos/{todo_id}", headers=_headers(users["student"]))
    assert student_view.status_code == 200


def test_teacher_create_can_include_due_date(client, users):
    created = _create_todo(
        client,
        users,
        assignee_id=users["student"],
        due_date="2030-05-01",
    )
    assert created["due_date"] == "2030-05-01"


def test_teacher_create_without_assignee_assigns_all_students(client, users):
    second_student = user_repo.create("Another Student", "student")

    response = client.post(
        "/api/todos",
        json={"title": "Group Work"},
        headers=_headers(users["teacher"]),
    )
    assert response.status_code == 201
    data = response.get_json()
    assert isinstance(data, list)
    assignee_ids = {item["assignee"]["id"] for item in data}
    assert assignee_ids == {users["student"], second_student.id}

    student_one = client.get("/api/todos", headers=_headers(users["student"])).get_json()
    student_two = client.get("/api/todos", headers=_headers(second_student.id)).get_json()
    assert len(student_one) == 1
    assert len(student_two) == 1


def test_teacher_list_filters_by_owner(client, users):
    other_teacher = user_repo.create("Other Teacher", "teacher")
    _create_todo(client, users, title="Our class")
    client.post(
        "/api/todos",
        json={"title": "Other class"},
        headers=_headers(other_teacher.id),
    )

    response = client.get("/api/todos", headers=_headers(users["teacher"]))
    items = response.get_json()
    assert len(items) == 1
    assert items[0]["title"] == "Our class"


def test_student_list_only_assigned(client, users):
    other_student = user_repo.create("Other Student", "student")

    first = _create_todo(client, users, title="Math", assignee_id=users["student"])
    _create_todo(client, users, title="English", assignee_id=other_student.id)

    response = client.get("/api/todos", headers=_headers(users["student"]))
    data = response.get_json()
    assert len(data) == 1
    assert data[0]["id"] == first["id"]


def test_teacher_can_modify_and_delete(client, users):
    todo_id = _create_todo(client, users, description="Write report")["id"]

    patch_resp = client.patch(
        f"/api/todos/{todo_id}",
        json={"description": "Write report (final)", "due_date": "2030-06-01"},
        headers=_headers(users["teacher"]),
    )
    assert patch_resp.status_code == 200
    data = patch_resp.get_json()
    assert data["description"] == "Write report (final)"
    assert data["due_date"] == "2030-06-01"

    delete_resp = client.delete(f"/api/todos/{todo_id}", headers=_headers(users["teacher"]))
    assert delete_resp.status_code == 204


def test_student_can_mark_completed_sets_timestamp(client, users):
    todo = _create_todo(client, users, assignee_id=users["student"])

    patch_resp = client.patch(
        f"/api/todos/{todo['id']}",
        json={"completed": True},
        headers=_headers(users["student"]),
    )
    assert patch_resp.status_code == 200
    data = patch_resp.get_json()
    assert data["completed"] is True
    assert data["completed_at"] is not None

    patch_resp = client.patch(
        f"/api/todos/{todo['id']}",
        json={"completed": False},
        headers=_headers(users["student"]),
    )
    assert patch_resp.status_code == 200
    assert patch_resp.get_json()["completed_at"] is None


def test_student_cannot_change_other_fields(client, users):
    todo = _create_todo(client, users, assignee_id=users["student"])

    patch_resp = client.patch(
        f"/api/todos/{todo['id']}",
        json={"description": "Change"},
        headers=_headers(users["student"]),
    )
    assert patch_resp.status_code == 403


def test_student_cannot_complete_unassigned(client, users):
    other_student = user_repo.create("Other Student", "student")
    todo = _create_todo(client, users, assignee_id=other_student.id)

    patch_resp = client.patch(
        f"/api/todos/{todo['id']}",
        json={"completed": True},
        headers=_headers(users["student"]),
    )
    assert patch_resp.status_code == 403


def test_teacher_can_reassign(client, users):
    first_student = users["student"]
    second_student = user_repo.create("Transfer", "student").id
    todo = _create_todo(client, users, assignee_id=first_student)

    assign_resp = client.post(
        f"/api/todos/{todo['id']}/assign",
        json={"assignee_id": second_student},
        headers=_headers(users["teacher"]),
    )
    assert assign_resp.status_code == 200
    assert assign_resp.get_json()["assignee"]["id"] == second_student

    list_resp = client.get("/api/todos", headers=_headers(second_student))
    assert len(list_resp.get_json()) == 1

    original_student_resp = client.get("/api/todos", headers=_headers(first_student))
    assert original_student_resp.get_json() == []

def test_teacher_can_delete_todo_via_dashboard(client, users):
    todo_id = _create_todo(client, users, description="Temp")["id"]

    resp = client.post(
        f"/teachers/{users['teacher']}/todos/{todo_id}/delete",
        follow_redirects=True,
    )
    assert resp.status_code == 200
    assert todo_repo.get(todo_id) is None


def test_teacher_can_add_and_remove_student_via_dashboard(client, users):
    add_resp = client.post(
        f"/teachers/{users['teacher']}/students",
        data={"name": "New Student"},
        follow_redirects=True,
    )
    assert add_resp.status_code == 200
    new_student = user_repo.find_by_name("New Student")
    assert new_student is not None

    todo_repo.create(
        title="Art",
        description="Draw",
        completed=False,
        owner_id=users["teacher"],
        assignee_id=new_student.id,
        due_date=None,
    )

    delete_resp = client.post(
        f"/teachers/{users['teacher']}/students/{new_student.id}/delete",
        follow_redirects=True,
    )
    assert delete_resp.status_code == 200
    assert user_repo.get(new_student.id) is None
    assert not list(todo_repo.list(assignee_id=new_student.id))
