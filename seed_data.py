from __future__ import annotations

import argparse

from todo_service import db
from todo_service.seed import seed_example_data


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed example data into the TODO service database.")
    parser.add_argument(
        "--database",
        default=db.DATABASE_DEFAULT,
        help="Path to the SQLite database file (default: %(default)s)",
    )
    args = parser.parse_args()

    db.configure(args.database)
    db.init_schema()
    summary = seed_example_data()
    db.close_connection()

    created_users = summary["created_users"]
    created_todos = summary["created_todos"]
    print(f"Seed completed: {created_users} new user(s), {created_todos} new todo(s).")


if __name__ == "__main__":
    main()
