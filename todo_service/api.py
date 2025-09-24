from __future__ import annotations

from http import HTTPStatus
from typing import Any, Dict, Optional

from flask import Blueprint, Response, jsonify, request
from .repository import NO_UPDATE, Todo
from .repository import Todo
from .services import (
    NotFoundError,
    PermissionDeniedError,
    ServiceError,
    ValidationError,
    normalize_due_date,
    todo_service,
    user_service,
)

AUTH_HEADER = "X-User-Id"


def _json_error(message: str, status: HTTPStatus, *, detail: Optional[str] = None) -> Response:
    payload: Dict[str, Any] = {"error": message}
    if detail:
        payload["detail"] = detail
    return jsonify(payload), status


def _handle_service_error(exc: ServiceError) -> Response:
    if isinstance(exc, ValidationError):
        status = HTTPStatus.BAD_REQUEST
    elif isinstance(exc, NotFoundError):
        status = HTTPStatus.NOT_FOUND
    elif isinstance(exc, PermissionDeniedError):
        status = HTTPStatus.FORBIDDEN
    else:
        status = HTTPStatus.INTERNAL_SERVER_ERROR
    return _json_error(str(exc), status)


def _require_user():
    raw_user_id = request.headers.get(AUTH_HEADER)
    if not raw_user_id:
        return None, _json_error("인증 정보가 필요합니다.", HTTPStatus.UNAUTHORIZED)

    try:
        user_id = int(raw_user_id)
    except (TypeError, ValueError):
        return None, _json_error("잘못된 사용자 ID입니다.", HTTPStatus.UNAUTHORIZED)

    try:
        user = user_service.get_user(user_id)
    except NotFoundError:
        return None, _json_error("존재하지 않는 사용자입니다.", HTTPStatus.UNAUTHORIZED)

    return user, None


def _validate_payload(data: Dict[str, Any], *, require_title: bool = False) -> Dict[str, Any]:
    if data is None:
        raise ValueError("JSON 본문이 필요합니다.")

    validated: Dict[str, Any] = {}

    if "title" in data:
        title = data["title"]
        if not isinstance(title, str) or not title.strip():
            raise ValueError("title 필드는 비어 있지 않은 문자열이어야 합니다.")
        validated["title"] = title.strip()
    elif require_title:
        raise ValueError("title 필드는 필수입니다.")

    if "description" in data:
        description = data["description"]
        if description is not None and not isinstance(description, str):
            raise ValueError("description 필드는 문자열이거나 null 이어야 합니다.")
        validated["description"] = description or ""

    if "completed" in data:
        completed = data["completed"]
        if not isinstance(completed, bool):
            raise ValueError("completed 필드는 불리언이어야 합니다.")
        validated["completed"] = completed

    if "assignee_id" in data:
        assignee_id = data["assignee_id"]
        if assignee_id is not None and not isinstance(assignee_id, int):
            raise ValueError("assignee_id 필드는 정수거나 null 이어야 합니다.")
        validated["assignee_id"] = assignee_id

    if "due_date" in data:
        try:
            validated["due_date"] = normalize_due_date(data["due_date"])
        except ValidationError as exc:
            raise ValueError(str(exc)) from exc

    return validated


def _serialize_todo(todo: Todo) -> Dict[str, Any]:
    data = todo.to_dict()
    try:
        owner = user_service.get_user(todo.owner_id)
        data["owner"] = owner.to_dict()
    except NotFoundError:
        data["owner"] = None

    if todo.assignee_id is not None:
        try:
            assignee = user_service.get_user(todo.assignee_id)
            data["assignee"] = assignee.to_dict()
        except NotFoundError:
            data["assignee"] = None
    else:
        data["assignee"] = None
    return data


todo_api = Blueprint("todo_api", __name__, url_prefix="/api/todos")
user_api = Blueprint("user_api", __name__, url_prefix="/api/users")


@user_api.get("")
def list_users() -> Response:
    users = [user.to_dict() for user in user_service.list_users()]
    return jsonify(users)


@user_api.post("")
def create_user() -> Response:
    payload = request.get_json(silent=True) or {}
    name = payload.get("name")
    role = payload.get("role")

    if not isinstance(name, str) or not name.strip():
        return _json_error("name 필드는 비어 있지 않은 문자열이어야 합니다.", HTTPStatus.BAD_REQUEST)
    if role not in {"teacher", "student"}:
        return _json_error("role 필드는 teacher 또는 student 여야 합니다.", HTTPStatus.BAD_REQUEST)

    user = user_service.create_user(name.strip(), role)
    return jsonify(user.to_dict()), HTTPStatus.CREATED


@todo_api.get("")
def list_todos() -> Response:
    user, error = _require_user()
    if error:
        return error

    try:
        if user.role == "teacher":
            todos = todo_service.list_for_teacher(user.id)
        else:
            todos = todo_service.list_for_student(user.id)
    except ServiceError as exc:
        return _handle_service_error(exc)

    return jsonify([_serialize_todo(todo) for todo in todos])


@todo_api.post("")
def create_todo() -> Response:
    user, error = _require_user()
    if error:
        return error

    try:
        payload = request.get_json(force=False, silent=False)
    except Exception as exc:  # noqa: BLE001
        return _json_error("JSON 본문을 파싱하지 못했습니다.", HTTPStatus.BAD_REQUEST, detail=str(exc))

    try:
        data = _validate_payload(payload, require_title=True)
    except ValueError as exc:
        return _json_error(str(exc), HTTPStatus.BAD_REQUEST)

    try:
        created = todo_service.create_todos(
            user.id,
            title=data["title"],
            description=data.get("description", ""),
            due_date=data.get("due_date"),
            completed=data.get("completed", False),
            assignee_id=data.get("assignee_id"),
        )
    except ServiceError as exc:
        return _handle_service_error(exc)

    if len(created) == 1:
        return jsonify(_serialize_todo(created[0])), HTTPStatus.CREATED
    return jsonify([_serialize_todo(todo) for todo in created]), HTTPStatus.CREATED


@todo_api.get("/<int:todo_id>")
def get_todo(todo_id: int) -> Response:
    user, error = _require_user()
    if error:
        return error

    try:
        if user.role == "teacher":
            todo = todo_service.verify_teacher_access(todo_id, user.id)
        else:
            todo = todo_service.verify_student_access(todo_id, user.id)
    except ServiceError as exc:
        return _handle_service_error(exc)

    return jsonify(_serialize_todo(todo))


@todo_api.post("/<int:todo_id>/assign")
def assign_todo(todo_id: int) -> Response:
    user, error = _require_user()
    if error:
        return error

    payload = request.get_json(silent=True) or {}
    assignee_id = payload.get("assignee_id")
    if assignee_id is None:
        return _json_error("assignee_id 필드가 필요합니다.", HTTPStatus.BAD_REQUEST)

    try:
        updated = todo_service.assign_todo(todo_id, user.id, assignee_id)
    except ServiceError as exc:
        return _handle_service_error(exc)

    return jsonify(_serialize_todo(updated))


@todo_api.put("/<int:todo_id>")
def replace_todo(todo_id: int) -> Response:
    user, error = _require_user()
    if error:
        return error

    payload = request.get_json(silent=True)
    try:
        data = _validate_payload(payload or {}, require_title=True)
    except ValueError as exc:
        return _json_error(str(exc), HTTPStatus.BAD_REQUEST)

    try:
        updated = todo_service.update_todo_by_teacher(
            todo_id,
            user.id,
            title=data["title"],
            description=data.get("description", ""),
            due_date=data.get("due_date", None),
            completed=data.get("completed"),
            assignee_id=data.get("assignee_id", NO_UPDATE),
        )
    except ServiceError as exc:
        return _handle_service_error(exc)

    return jsonify(_serialize_todo(updated))


@todo_api.patch("/<int:todo_id>")
def update_todo(todo_id: int) -> Response:
    user, error = _require_user()
    if error:
        return error

    payload = request.get_json(silent=True) or {}

    if user.role == "teacher":
        try:
            data = _validate_payload(payload)
        except ValueError as exc:
            return _json_error(str(exc), HTTPStatus.BAD_REQUEST)

        try:
            updated = todo_service.update_todo_by_teacher(
                todo_id,
                user.id,
                title=data.get("title"),
                description=data.get("description"),
                due_date=data.get("due_date", NO_UPDATE),
                completed=data.get("completed"),
                assignee_id=data.get("assignee_id", NO_UPDATE),
            )
        except ServiceError as exc:
            return _handle_service_error(exc)
        return jsonify(_serialize_todo(updated))

    if set(payload.keys()) != {"completed"}:
        return _json_error("학생은 완료 상태만 변경할 수 있습니다.", HTTPStatus.FORBIDDEN)

    completed_value = payload.get("completed")
    if not isinstance(completed_value, bool):
        return _json_error("completed 필드는 불리언이어야 합니다.", HTTPStatus.BAD_REQUEST)

    try:
        updated = todo_service.update_todo_by_student(todo_id, user.id, completed_value)
    except ServiceError as exc:
        return _handle_service_error(exc)
    return jsonify(_serialize_todo(updated))


@todo_api.delete("/<int:todo_id>")
def delete_todo(todo_id: int) -> Response:
    user, error = _require_user()
    if error:
        return error

    try:
        todo_service.delete_todo(todo_id, user.id)
    except ServiceError as exc:
        return _handle_service_error(exc)

    return Response(status=HTTPStatus.NO_CONTENT)
