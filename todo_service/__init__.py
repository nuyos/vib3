from __future__ import annotations

from flask import Flask

from . import db
from .api import todo_api, user_api


def init_app(app: Flask) -> None:
    """Register blueprints and initialise persistence for the given app."""
    database_path = app.config.get("DATABASE", db.DATABASE_DEFAULT)
    db.configure(database_path)
    db.init_schema()

    app.register_blueprint(user_api)
    app.register_blueprint(todo_api)
