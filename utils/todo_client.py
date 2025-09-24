from __future__ import annotations

from json import JSONDecodeError
from typing import Any, Dict, Optional

import requests


class TodoClientError(RuntimeError):
    """Raised when the TODO API request fails."""


def get_todo_item(todo_id: int, timeout: float = 5.0) -> Optional[Dict[str, Any]]:
    """지정된 ID의 할 일 항목을 API로부터 가져옵니다."""
    api_url = f"https://jsonplaceholder.typicode.com/todos/{todo_id}"

    try:
        response = requests.get(api_url, timeout=timeout)
    except requests.Timeout as exc:
        raise TodoClientError(
            f"TODO API 응답이 {timeout}초 이내에 도착하지 않았습니다."
        ) from exc
    except requests.ConnectionError as exc:
        raise TodoClientError("TODO API에 연결할 수 없습니다.") from exc
    except requests.RequestException as exc:
        raise TodoClientError("TODO 항목 조회 중 네트워크 오류가 발생했습니다.") from exc

    if response.status_code == 404:
        return None

    try:
        response.raise_for_status()
    except requests.HTTPError as exc:
        raise TodoClientError(
            f"TODO 항목 조회가 실패했습니다. 상태 코드: {response.status_code}"
        ) from exc

    try:
        return response.json()
    except JSONDecodeError as exc:
        raise TodoClientError("API 응답을 JSON으로 디코딩하지 못했습니다.") from exc


if __name__ == "__main__":
    print("--- 실행 코드 ---")
    # 1. 성공하는 경우
    try:
        todo = get_todo_item(1, timeout=3.0)
        if todo is None:
            print("To Do item not found for ID 1")
        else:
            print("To Do item received:", todo)
    except TodoClientError as exc:
        print("To Do item request failed:", exc)

    # 2. 실패하는 경우
    try:
        non_existent_todo = get_todo_item(9999, timeout=3.0)
        if non_existent_todo is None:
            print("To Do item not found for ID 9999")
        else:
            print("To Do item received:", non_existent_todo)
    except TodoClientError as exc:
        print("To Do item request failed:", exc)
