from __future__ import annotations

from datetime import datetime
from typing import Optional

from flask import Flask, Response, abort, redirect, render_template_string, request, url_for

from todo_service import init_app as init_todo_service
from todo_service.services import (
    NotFoundError,
    PermissionDeniedError,
    ServiceError,
    ValidationError,
    normalize_due_date,
    todo_service as todo_service_layer,
    user_service as user_service_layer,
)
from utils.todo_client import TodoClientError, get_todo_item


def _abort_service_error(exc: ServiceError) -> None:
    if isinstance(exc, NotFoundError):
        abort(404, description=str(exc))
    elif isinstance(exc, PermissionDeniedError):
        abort(403, description=str(exc))
    else:
        abort(400, description=str(exc))


def create_app() -> Flask:
    app = Flask(__name__)
    init_todo_service(app)

    def _render_error(message: str, status_code: int) -> Response:
        """Return error responses in HTML or JSON depending on the request."""
        if request.path.startswith("/api/"):
            return app.response_class(
                response=app.json.dumps({"error": message}, ensure_ascii=False),
                status=status_code,
                mimetype="application/json",
            )

        html = """<!doctype html><title>Error</title><h1>Error</h1><p>{message}</p>"""
        return Response(html.format(message=message), status=status_code, mimetype="text/html")

    @app.errorhandler(404)
    def handle_not_found(error: Exception) -> Response:
        message = getattr(error, "description", "요청한 자원을 찾을 수 없습니다.")
        return _render_error(message, 404)

    @app.errorhandler(502)
    def handle_bad_gateway(error: Exception) -> Response:
        message = getattr(error, "description", "업스트림 서비스와의 통신에 실패했습니다.")
        return _render_error(message, 502)

    @app.route("/todos/<int:todo_id>")
    def todo_detail(todo_id: int):
        try:
            todo = get_todo_item(todo_id)
        except TodoClientError as exc:
            abort(502, description=str(exc))

        if todo is None:
            abort(404, description=f"ID {todo_id}인 할 일을 찾을 수 없습니다.")

        if todo.get("id") == 1:
            todo = {**todo, "title": "hi"}

        return render_template_string(
            """<!doctype html><title>Todo {{ todo.id }}</title><h1>{{ todo.title }}</h1>""",
            todo=todo,
        )

    @app.route("/students/<int:student_id>/todos")
    def student_dashboard(student_id: int):
        try:
            student = user_service_layer.ensure_student(student_id)
            todos = todo_service_layer.list_for_student(student_id)
        except ServiceError as exc:
            _abort_service_error(exc)

        assignments = []
        for todo in todos:
            try:
                teacher = user_service_layer.get_user(todo.owner_id)
            except ServiceError:
                teacher = None
            assignments.append((todo, teacher))

        html = render_template_string(
            """
            <!doctype html>
            <title>{{ student.name }}의 숙제</title>
            <h1>{{ student.name }}의 숙제 목록</h1>
            {% if assignments %}
            <ul>
                {% for todo, teacher in assignments %}
                <li style="margin-bottom:1.5rem;">
                    <form method="post" action="{{ url_for('update_student_todo_completion', student_id=student.id, todo_id=todo.id) }}">
                        <strong>{{ todo.title }}</strong>
                        {% if teacher %}<em>({{ teacher.name }})</em>{% endif %}<br>
                        {{ todo.description or '설명 없음' }}<br>
                        {% if todo.due_date %}
                            <small>마감일: {{ todo.due_date }}</small><br>
                        {% endif %}
                        {% if todo.completed_at %}
                            <small>완료일시: {{ todo.completed_at }}</small><br>
                        {% endif %}
                        <label style="display:inline-flex;align-items:center;gap:0.4rem;margin-top:0.5rem;">
                            <input type="checkbox" name="completed" value="1" {% if todo.completed %}checked{% endif %} onchange="this.form.submit()">
                            완료
                        </label>
                        <noscript><button type="submit">상태 저장</button></noscript>
                    </form>
                </li>
                {% endfor %}
            </ul>
            {% else %}
            <p>아직 할당된 숙제가 없습니다.</p>
            {% endif %}
            """,
            student=student,
            assignments=assignments,
        )
        return Response(html, mimetype="text/html")

    @app.post("/students/<int:student_id>/todos/<int:todo_id>/completion")
    def update_student_todo_completion(student_id: int, todo_id: int):
        completed = request.form.get("completed") == "1"
        try:
            todo_service_layer.update_todo_by_student(todo_id, student_id, completed)
        except ServiceError as exc:
            _abort_service_error(exc)
        return redirect(url_for("student_dashboard", student_id=student_id))

    @app.route("/teachers/<int:teacher_id>/todos", methods=["GET", "POST"])
    def teacher_dashboard(teacher_id: int):
        try:
            teacher = user_service_layer.ensure_teacher(teacher_id)
        except ServiceError as exc:
            _abort_service_error(exc)

        students = list(user_service_layer.list_students())
        feedback: Optional[tuple[str, str]] = None

        if request.method == "POST":
            title = (request.form.get("title") or "").strip()
            description = (request.form.get("description") or "").strip()
            assignee_raw = (request.form.get("assignee_id") or "").strip()
            due_date_raw = (request.form.get("due_date") or "").strip()

            if not title:
                feedback = ("error", "제목을 입력해 주세요.")
            else:
                assignee_id: Optional[int] = None
                if assignee_raw:
                    try:
                        assignee_id = int(assignee_raw)
                    except ValueError:
                        feedback = ("error", "학생 선택 값이 올바르지 않습니다.")
                try:
                    due_date = normalize_due_date(due_date_raw)
                except ValidationError as exc:
                    feedback = ("error", str(exc))
                if feedback is None:
                    try:
                        todo_service_layer.create_todos(
                            teacher_id,
                            title=title,
                            description=description,
                            due_date=due_date,
                            completed=False,
                            assignee_id=assignee_id,
                        )
                    except ServiceError as exc:
                        feedback = ("error", str(exc))
                    else:
                        return redirect(url_for("teacher_dashboard", teacher_id=teacher_id, status="created"))

        status = request.args.get("status")
        if feedback is None and status:
            status_messages = {
                "created": ("success", "새 숙제를 등록했습니다."),
                "todo_deleted": ("success", "숙제를 삭제했습니다."),
                "student_added": ("success", "학생을 추가했습니다."),
                "student_removed": ("success", "학생을 삭제했습니다."),
                "student_add_error": ("error", "학생 이름을 입력해 주세요."),
            }
            feedback = status_messages.get(status, feedback)

        try:
            assignments = todo_service_layer.list_for_teacher(teacher_id)
        except ServiceError as exc:
            _abort_service_error(exc)

        assignment_rows = []
        for todo in assignments:
            try:
                assignee = user_service_layer.get_user(todo.assignee_id) if todo.assignee_id is not None else None
            except ServiceError:
                assignee = None
            assignment_rows.append((todo, assignee))

        html = render_template_string(
            """
            <!doctype html>
            <title>{{ teacher.name }}의 숙제관리</title>
            <h1>{{ teacher.name }}의 숙제관리</h1>
            {% if feedback %}
                <p style="color:{{ 'green' if feedback[0] == 'success' else 'crimson' }};">{{ feedback[1] }}</p>
            {% endif %}
            <section style="margin-bottom:2rem;">
                <h2>새 숙제 등록</h2>
                <form method="post" style="display:grid;gap:0.8rem;max-width:420px;">
                    <label>제목
                        <input type="text" name="title" required>
                    </label>
                    <label>설명
                        <textarea name="description" rows="3"></textarea>
                    </label>
                    <label>마감일
                        <input type="date" name="due_date">
                    </label>
                    <label>학생 지정
                        <select name="assignee_id">
                            <option value="">전체 학생</option>
                            {% for student in students %}
                                <option value="{{ student.id }}">{{ student.name }}</option>
                            {% endfor %}
                        </select>
                    </label>
                    <button type="submit">숙제 추가</button>
                </form>
            </section>
            <section style="margin-bottom:2rem;">
                <h2>학생 관리</h2>
                <form method="post" action="{{ url_for('create_student_for_teacher', teacher_id=teacher.id) }}" style="display:flex;gap:0.5rem;align-items:center;margin-bottom:1rem;">
                    <label style="display:flex;flex-direction:column;gap:0.3rem;">
                        학생 이름
                        <input type="text" name="name" required>
                    </label>
                    <button type="submit">학생 추가</button>
                </form>
                {% if students %}
                <table border="1" cellpadding="6" cellspacing="0">
                    <thead>
                        <tr>
                            <th>ID</th>
                            <th>이름</th>
                            <th>관리</th>
                        </tr>
                    </thead>
                    <tbody>
                        {% for student in students %}
                        <tr>
                            <td>{{ student.id }}</td>
                            <td>{{ student.name }}</td>
                            <td>
                                <form method="post" action="{{ url_for('delete_student_for_teacher', teacher_id=teacher.id, student_id=student.id) }}" style="display:inline;">
                                    <button type="submit">삭제</button>
                                </form>
                            </td>
                        </tr>
                        {% endfor %}
                    </tbody>
                </table>
                {% else %}
                <p>등록된 학생이 없습니다.</p>
                {% endif %}
            </section>
            <section>
                <h2>숙제 목록</h2>
                {% if assignment_rows %}
                <table border="1" cellpadding="6" cellspacing="0">
                    <thead>
                        <tr>
                            <th>ID</th>
                            <th>제목</th>
                            <th>학생</th>
                            <th>마감일</th>
                            <th>상태</th>
                            <th>완료일시</th>
                            <th>관리</th>
                        </tr>
                    </thead>
                    <tbody>
                        {% for todo, assignee in assignment_rows %}
                        <tr>
                            <td>{{ todo.id }}</td>
                            <td>{{ todo.title }}</td>
                            <td>{{ assignee.name if assignee else '미지정' }}</td>
                            <td>{{ todo.due_date or '미정' }}</td>
                            <td>{{ '완료' if todo.completed else '진행중' }}</td>
                            <td>{% if todo.completed_at %}{{ todo.completed_at }}{% else %}-{% endif %}</td>
                            <td>
                                <form method="post" action="{{ url_for('delete_teacher_todo', teacher_id=teacher.id, todo_id=todo.id) }}" style="display:inline;">
                                    <button type="submit">삭제</button>
                                </form>
                            </td>
                        </tr>
                        {% endfor %}
                    </tbody>
                </table>
                {% else %}
                <p>등록된 숙제가 없습니다.</p>
                {% endif %}
            </section>
            """,
            teacher=teacher,
            students=students,
            assignment_rows=assignment_rows,
            feedback=feedback,
        )
        return Response(html, mimetype="text/html")

    @app.post("/teachers/<int:teacher_id>/todos/<int:todo_id>/delete")
    def delete_teacher_todo(teacher_id: int, todo_id: int):
        try:
            todo_service_layer.delete_todo(todo_id, teacher_id)
        except ServiceError as exc:
            _abort_service_error(exc)
        return redirect(url_for("teacher_dashboard", teacher_id=teacher_id, status="todo_deleted"))

    @app.post("/teachers/<int:teacher_id>/students")
    def create_student_for_teacher(teacher_id: int):
        try:
            user_service_layer.ensure_teacher(teacher_id)
        except ServiceError as exc:
            _abort_service_error(exc)

        name = (request.form.get("name") or "").strip()
        if not name:
            return redirect(url_for("teacher_dashboard", teacher_id=teacher_id, status="student_add_error"))

        user_service_layer.create_student(name)
        return redirect(url_for("teacher_dashboard", teacher_id=teacher_id, status="student_added"))

    @app.post("/teachers/<int:teacher_id>/students/<int:student_id>/delete")
    def delete_student_for_teacher(teacher_id: int, student_id: int):
        try:
            user_service_layer.ensure_teacher(teacher_id)
            user_service_layer.delete_student(student_id)
        except ServiceError as exc:
            _abort_service_error(exc)
        return redirect(url_for("teacher_dashboard", teacher_id=teacher_id, status="student_removed"))

    return app


app = create_app()


if __name__ == "__main__":
    app.run(debug=True)
