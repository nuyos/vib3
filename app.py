from __future__ import annotations

from flask import Flask, Response, abort, render_template_string

from utils.todo_client import TodoClientError, get_todo_item


app = Flask(__name__)


def _render_error(message: str, status_code: int) -> Response:
    """Return a simple HTML error response."""
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


if __name__ == "__main__":
    app.run(debug=True)
