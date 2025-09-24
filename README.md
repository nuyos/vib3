# 선생님·학생 숙제 관리 웹앱

Flask 기반으로 만든 학습용 웹 서비스입니다. 선생님이 여러 학생에게 숙제를 배포하고, 학생이 웹에서 완료 여부를 체크하면 교사가 완료 시간까지 확인할 수 있는 흐름을 제공합니다. REST API와 간단한 HTML 대시보드, 그리고 서비스/저장소가 분리된 구조를 통해 웹 백엔드 기본기를 연습할 수 있습니다.

---

## 1. 핵심 기능
- **교사 대시보드** (`/teachers/<teacher_id>/todos`)
  - 숙제 생성: 특정 학생 또는 전체 학생에게 한 번에 배포
  - 숙제 삭제 및 완료 현황 확인(마감일, 완료일시 표시)
  - 학생 관리: 학생 추가·삭제
- **학생 대시보드** (`/students/<student_id>/todos`)
  - 배정된 숙제 목록 확인, 체크박스로 완료 토글
  - 완료 시각이 자동 기록되어 교사 페이지에 반영
- **REST API** (`/api/users`, `/api/todos` 등)
  - `X-User-Id` 헤더 기반의 간단한 인증 흐름
  - CRUD, 전체 배포, 완료 처리 시 타임스탬프 갱신
- **시드 스크립트** (`seed_data.py`)
  - 예시 교사/학생/숙제를 한 번에 삽입하여 데모 세팅

---

## 2. 기술 스택
- Python 3.13
- Flask (웹 프레임워크)
- SQLite (저장소)
- Pytest (테스트)
- 기타: requests (외부 TODO 샘플 확인용)

---

## 3. 아키텍처 & 폴더 구조
서비스 계층을 명확히 나눈 3-레이어 구조입니다.

```
dataschool/
├── app.py                      # Flask 라우트 & UI
├── seed_data.py                # 시드 실행 스크립트
├── todo_service/
│   ├── api.py                  # REST API (Blueprint)
│   ├── services.py             # 도메인/비즈니스 로직
│   ├── repository.py           # SQLite 데이터 접근 레이어
│   ├── db.py                   # 커넥션 및 스키마 초기화
│   └── seed.py                 # 서비스 기반 시드 로직
├── tests/
│   └── test_todo_api.py        # 통합 테스트 (pytest)
└── utils/
    └── todo_client.py          # 외부 TODO API 샘플 클라이언트
```

- **UI**: `app.py`가 Flask 라우트를 정의 (교사/학생 페이지, 에러 처리 등)
- **Service**: `todo_service/services.py`가 권한 검사·배포 로직·완료 기록 등 핵심 규칙 담당
- **Repository**: `todo_service/repository.py`가 SQLite와 직접 통신, Service가 데이터 접근을 위임
- **DB 초기화**: `todo_service/db.py`는 한 번만 연결을 생성하고 외래키/스키마를 구성

---

## 4. 실행 방법
1. **가상환경 & 패키지**
   ```bash
   python -m venv venv
   .\venv\Scripts\activate        # PowerShell 기준 (macOS/Linux는 source venv/bin/activate)
   pip install flask pytest
   ```
   (프로젝트에 `requirements.txt`를 만들어 두면 `pip install -r requirements.txt`로 대체 가능)

2. **시드 & 실행**
   ```bash
   python seed_data.py            # 예시 교사/학생/숙제 삽입
   python app.py
   ```

3. **브라우저 접속**
   - 교사 페이지: `http://127.0.0.1:5000/teachers/1/todos`
   - 학생 페이지: `http://127.0.0.1:5000/students/2/todos` (시드 기준 학생 ID는 2, 3, 4)

---

## 5. REST API 요약
- `POST /api/users` – 사용자 생성 (role: `teacher` 또는 `student`)
- `GET /api/todos` – `X-User-Id`에 따라 교사/학생 별 목록 조회
- `POST /api/todos`
  - `assignee_id` 지정 시 특정 학생에게 숙제 배포
  - `assignee_id` 미지정 시 모든 학생에게 동일 숙제 복제
- `PATCH /api/todos/<id>` – 교사: 제목/설명/마감일/배정 변경, 학생: 완료 상태 토글
- `DELETE /api/todos/<id>` – 교사만 삭제 가능

> **인증**: 간단한 데모용으로 `X-User-Id` 헤더에 사용자 ID를 넣으면 해당 사용자 권한으로 동작합니다.

---

## 6. 테스트
pytest 기반으로 REST 흐름과 UI 액션을 검증합니다.
```bash
pytest
```
검증 내용: 전체 배포, 완료 토글 시 타임스탬프 기록, 교사/학생 권한 제한, 대시보드 액션 등.

---

## 7. 향후 개선 아이디어
- JWT/세션 기반 인증, CSRF 방어, 입력 폼 검증 강화
- SQLite → PostgreSQL 등으로 확장 및 커넥션 풀 구성
- 레이아웃 템플릿/정적 자원 분리하여 UI 고도화
- N+1 쿼리 최적화를 위한 조인 뷰 또는 캐싱 도입
- Docker Compose로 실행/테스트 환경 자동화

---

## 8. 스크린샷
<img width="483" height="803" alt="img1" src="https://github.com/user-attachments/assets/c4d64980-d455-48df-bfe2-0b4086a20d7c" />

<img width="266" height="379" alt="img2" src="https://github.com/user-attachments/assets/1ac9742e-cd42-4a59-a96c-096c279a5889" />


