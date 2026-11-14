"""데모 DB 스키마 (SQLite + SQLModel).

서식 입력값은 JSON 컬럼 하나에 통째로 넣는다. 데모 단계에서 서식 필드가 계속
바뀌는데 그때마다 마이그레이션을 하는 건 낭비다. 심사·집계에 실제로 쓰이는
값만 P3에서 별도 컬럼으로 승격한다.
"""

from contextlib import contextmanager
from contextvars import ContextVar
from datetime import date, datetime
from pathlib import Path
from typing import Any, Optional

from sqlalchemy import JSON, Column, UniqueConstraint
from sqlmodel import Field, Session, SQLModel, create_engine
from .rules.programs import JOB_PACKAGE

DB_PATH = Path(__file__).resolve().parents[1] / "demo.db"
engine = create_engine(f"sqlite:///{DB_PATH}", connect_args={"check_same_thread": False})
_session_bind = ContextVar("demo_session_bind", default=None)


class Application(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    #: 엔진 `Applicant.applicant_id` 와 같은 키. 담당자가 원본과 매칭하는 유일 키.
    application_no: str = Field(index=True, unique=True)
    program_code: str = Field(index=True)
    #: 신청서 생성 시 고정된 사업 기준 버전. 수정하지 않는다.
    criteria_version: Optional[int] = Field(default=None, index=True)
    #: draft | submitted | reviewing | decided
    status: str = Field(default="draft", index=True)
    #: 서식1 입력값 전체
    form1_json: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    #: 서식2 자가진단 답변 {문항번호: "예"|"아니오"}
    self_check_json: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    #: 서식5 입력값(서명 이미지는 consent 테이블에 별도 저장)
    form5_json: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    #: 서류 체크리스트를 조립하는 입력 (근로유형·사업장 수·자필서명 여부)
    doc_context_json: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    #: 본인인증 결과 {name, birth, phone, method, verified_at, pledge_signature_path}.
    #: 업로드 서류가 '이 신청자의 것인지' 대조하는 기준. 신청서 입력값은 기준이 될 수 없다.
    #: 실서비스는 로그인 시 PASS·간편인증 결과(+CI)가 들어온다. 데모는 method="demo".
    identity_json: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    submitted_at: Optional[datetime] = None
    #: Applicant-only credentials and immutable submitted-form archive metadata.
    applicant_access_hash: Optional[str] = None
    written_forms_archive_path: Optional[str] = None
    written_forms_archive_count: Optional[int] = None


class ProgramCriteriaVersion(SQLModel, table=True):
    """사업별 심사 기준의 불변 버전 이력."""

    __table_args__ = (UniqueConstraint("program_code", "version"),)

    id: Optional[int] = Field(default=None, primary_key=True)
    program_code: str = Field(index=True)
    version: int
    criteria_json: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    changed_at: datetime = Field(default_factory=datetime.now)
    changed_role: str = "system"


class Consent(SQLModel, table=True):
    """동의 이력.

    수기 서명 없이도 '누가 언제 무엇에 동의했는지'를 남기는 것이 이 테이블의
    존재 이유다. 서식3·4는 체크만, 서식5는 서명 이미지까지 함께 남긴다.
    """

    id: Optional[int] = Field(default=None, primary_key=True)
    application_id: int = Field(index=True, foreign_key="application.id")
    #: privacy | unique_id | third_party | admin_info
    consent_type: str
    agreed: bool
    #: 서식5 전자서명 PNG 경로 (storage/ 하위). 자필 업로드면 그 파일 경로.
    signature_path: Optional[str] = None
    #: electronic | handwritten
    signature_kind: Optional[str] = None
    agreed_at: datetime = Field(default_factory=datetime.now)
    client_ip: Optional[str] = None
    user_agent: Optional[str] = None


class Document(SQLModel, table=True):
    """업로드 서류 한 건.

    같은 `doc_type`이 여러 슬롯에 올 수 있어(복수 사업장 근로확인서류) 슬롯 키를
    따로 둔다. 병합 PDF를 페이지 단위로 쪼갠 경우 `page_index`와
    `source_file_path`로 원본을 되짚는다.
    """

    id: Optional[int] = Field(default=None, primary_key=True)
    application_id: int = Field(index=True, foreign_key="application.id")
    #: 체크리스트 슬롯 식별자. 아직 배정되지 않은 병합 페이지는 "unassigned".
    slot_key: str
    #: OCR이 판별한 실제 서류 종류
    doc_type: Optional[str] = None
    #: 이 슬롯이 요구하는 서류 종류 (오분류 판정의 기준값)
    expected_doc_type: Optional[str] = None
    file_path: str
    file_format: str
    declared_issue_date: Optional[date] = None
    ocr_json: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    #: PASS | FAIL | NEEDS_REVIEW
    stage1_status: Optional[str] = None
    findings_json: list[Any] = Field(default_factory=list, sa_column=Column(JSON))
    #: 병합 PDF에서 쪼갠 경우 원본에서의 페이지 번호(0-based)
    page_index: Optional[int] = None
    #: 병합 PDF 원본 경로
    source_file_path: Optional[str] = None
    uploaded_at: datetime = Field(default_factory=datetime.now)


class SubsidyItem(SQLModel, table=True):
    """취업지원패키지에서 고른 지원 항목 1회차.

    항목별 복수 신청이 가능하므로(사업계획서 "복수선택가능") 회차마다 한 행이다.
    `granted_amount`는 `rules/subsidy.py`가 계산한 실지급액이고, 계산 근거는
    저장하지 않는다 — 한도가 바뀌면 근거 문장도 다시 계산돼야 하기 때문이다.
    """

    id: Optional[int] = Field(default=None, primary_key=True)
    application_id: int = Field(index=True, foreign_key="application.id")
    #: interview | suit | photo | certificate
    item_type: str
    #: 1-based 회차.
    count_index: int
    #: 정장비 회차가 연결된 면접확인서 회차. 중복 연결은 API에서 거부한다.
    linked_interview_index: Optional[int] = None
    #: 결제영수증 금액(원). 정액 항목(면접비)은 None.
    receipt_amount: Optional[int] = None
    granted_amount: int = 0
    created_at: datetime = Field(default_factory=datetime.now)


class Review(SQLModel, table=True):
    """제출 1건의 심사 결과.

    담당자 화면(`09-16-demo-officer`)이 읽는 유일한 테이블이다. 엔진이 만든
    `review_payload`와 데모가 채점한 `ScoreSheet`를 같이 들고 있어야, 담당자가
    "판정 사유"와 "점수 근거"를 한 화면에서 원본과 대조할 수 있다.

    ⚠️ 점수는 신청자에게 노출하지 않는다 (공고문: "평가결과는 공개하지 않음").
    마이페이지 응답(`/status`)은 이 테이블의 점수 컬럼을 절대 싣지 않는다.
    """

    id: Optional[int] = Field(default=None, primary_key=True)
    application_id: int = Field(index=True, foreign_key="application.id")
    #: PASS | FAIL | NEEDS_REVIEW (엔진 최종 판정)
    final_status: str = Field(index=True)
    stage1_status: Optional[str] = None
    stage2_status: Optional[str] = None
    #: `rules/scoring.ScoreSheet.as_dict()` — 항목별 basis·source_doc·bbox 포함
    score_json: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    total_score: Optional[int] = Field(default=None, index=True)
    #: 동점자 정렬 키 (시행지침 우선순위 ①~④)
    tiebreak_json: list[Any] = Field(default_factory=list, sa_column=Column(JSON))
    #: 엔진 `run_pipeline` 결과의 심사 요청 패키지 (+ file_ref 주입본)
    review_payload_json: dict[str, Any] = Field(
        default_factory=dict, sa_column=Column(JSON)
    )
    #: 서류 보완 기한. 보완이 허용되는 사업(취업패키지 7일)에서만 채워진다.
    #: 두배적금은 보완 자체가 없으므로 항상 None이다.
    supplement_deadline: Optional[datetime] = None
    #: 담당자 판단 — 여기부터는 officer 태스크가 채운다.
    officer_role: Optional[str] = None
    officer_decision: Optional[str] = None
    officer_memo: Optional[str] = None
    decided_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.now)


class ProgramPosting(SQLModel, table=True):
    """담당자가 올린 사업 한 건 (사업 저장소).

    `rules/programs.py`의 "program"은 코드에 박힌 규칙 세트이고, 이쪽은 담당자가
    게시하는 단위다. 둘을 잇는 것은 `rule_code` 하나뿐이다 — 규칙 세트가 있는
    기본 사업(취업지원패키지)만 값을 갖고, 그 값이 `Application.program_code`와
    같다. 담당자가 새로 올린 사업은 `rule_code`가 비어 있다.
    """

    #: 지운 작성 중 사업의 번호를 다시 쓰지 않는다. 번호가 저장 폴더 이름이라, 다시 쓰면
    #: 늦게 끝난 삭제가 새 사업의 파일을 지우거나 옛 주소가 다른 사업을 열 수 있다.
    __table_args__ = {"sqlite_autoincrement": True}


    id: Optional[int] = Field(default=None, primary_key=True)
    #: 앞뒤 공백을 뗀 1~100자.
    title: str
    apply_start: date
    apply_end: date
    #: draft | published | closed
    status: str = Field(default="draft", index=True)
    #: 기본 사업에서만 채운다. `rules/programs.py`의 사업 코드.
    rule_code: Optional[str] = Field(default=None, index=True, unique=True)
    #: 올린 파일의 원래 이름. 화면 표시용이다.
    notice_file_name: Optional[str] = None
    forms_file_name: Optional[str] = None
    #: 저장소 루트 기준 상대 경로 (`postings/<id>/notice.pdf`, `postings/<id>/forms.pdf`).
    notice_path: Optional[str] = None
    forms_path: Optional[str] = None
    #: 신청자 안내 문구. 3단계에서 채운다.
    guidance_text: str = ""
    #: 서식 템플릿. 3단계에서 채운다.
    template_json: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    #: 처음 게시한 시각. 마감했다가 다시 게시해도 바뀌지 않는다.
    published_at: Optional[datetime] = None


class ProgramApplicationSnapshot(SQLModel, table=True):
    """Immutable application-owned published form and document configuration."""
    application_id: int = Field(primary_key=True, foreign_key="application.id")
    posting_id: int = Field(index=True)
    snapshot_json: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=datetime.now)


class ProgramForm(SQLModel, table=True):
    """Uploaded form and officer-reviewed layout; additive for existing databases."""
    __table_args__ = {"sqlite_autoincrement": True}
    id: Optional[int] = Field(default=None, primary_key=True)
    posting_id: int = Field(index=True, foreign_key="programposting.id")
    file_name: str
    file_path: str
    layout_json: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    confirmed_hash: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)


#: 병합 PDF 페이지 중 어느 슬롯에도 배정되지 않은 것.
UNASSIGNED_SLOT = "unassigned"

#: 신청 상태. 마이페이지 진행 표시의 단일 소스다.
STATUS_DRAFT = "draft"
STATUS_SUBMITTED = "submitted"
STATUS_REVIEWING = "reviewing"
STATUS_DECIDED = "decided"

#: 사업(`ProgramPosting`) 상태. 작성 중 → 게시 → 마감, 마감한 사업은 다시 게시할 수 있다.
POSTING_DRAFT = "draft"
POSTING_PUBLISHED = "published"
POSTING_CLOSED = "closed"

#: 사업 저장소에 미리 올려 두는 기본 사업의 규칙 코드. 두배적금은 올리지 않는다.
BUILTIN_POSTING_CODES = (JOB_PACKAGE,)


def init_db() -> None:
    SQLModel.metadata.create_all(engine)
    _add_missing_columns()
    from .rules.criteria import ensure_defaults

    ensure_defaults()
    _ensure_builtin_postings()


def posting_today() -> date:
    """사업 저장소가 보는 오늘 날짜.

    기본 사업을 올릴 때와 접수 단계를 계산할 때 같은 날짜를 써야 한다. 두 곳이 다른
    날짜를 보면 방금 올린 사업이 올리자마자 마감으로 보일 수 있다. 시험은 이 함수
    하나만 바꿔 끼운다.
    """
    return date.today()


def _ensure_builtin_postings() -> None:
    """기본 사업을 사업 저장소에 한 번만 올린다.

    같은 `rule_code`의 행이 이미 있으면 아무것도 하지 않는다. 담당자가 기간이나 안내
    문구를 고치거나 마감한 뒤 서버를 다시 띄워도 그 행을 덮어쓰지 않는다.
    """
    from sqlmodel import select

    from .rules.programs import get_program

    today = posting_today()
    with get_session() as session:
        for code in BUILTIN_POSTING_CODES:
            existing = session.exec(
                select(ProgramPosting).where(ProgramPosting.rule_code == code)
            ).first()
            if existing is not None:
                continue
            program = get_program(code)
            start, end = program.apply_period
            # 실제 접수 기간이 이미 지났으면 데모에서 신청 흐름을 계속 쓸 수 있게
            # 종료일을 올리는 해의 12월 31일로 늘려 둔다. 규칙 세트의 기준일·심사
            # 기준은 그대로이고, 이 기간은 담당자가 사업 화면에서 바꿀 수 있다.
            if end < today:
                end = date(today.year, 12, 31)
            now = datetime.now()
            session.add(
                ProgramPosting(
                    title=program.name,
                    apply_start=start,
                    apply_end=end,
                    status=POSTING_PUBLISHED,
                    rule_code=code,
                    created_at=now,
                    updated_at=now,
                    published_at=now,
                )
            )
        session.commit()


def _add_missing_columns() -> None:
    """데모용 초경량 마이그레이션.

    SQLModel의 `create_all`은 이미 있는 테이블에 컬럼을 추가해 주지 않는다. 데모
    DB를 지웠다 다시 만들면 P1에서 작성한 신청 건이 날아가므로, 빠진 컬럼만
    ALTER로 붙인다. 정식 마이그레이션 도구는 데모 범위 밖이다.
    """
    from sqlalchemy import text

    with engine.connect() as conn:
        for table in SQLModel.metadata.sorted_tables:
            existing = {
                row[1] for row in conn.execute(text(f"PRAGMA table_info({table.name})"))
            }
            if not existing:
                continue
            for column in table.columns:
                if column.name in existing:
                    continue
                ddl = f"ALTER TABLE {table.name} ADD COLUMN {column.name} {column.type}"
                conn.execute(text(ddl))
        conn.commit()


def get_session() -> Session:
    connection = _session_bind.get()
    if connection is not None:
        # Handler commits flush into the caller's transaction, never commit it.
        return Session(connection, join_transaction_mode="rollback_only")
    return Session(engine)


@contextmanager
def session_transaction():
    """Atomically compose existing service handlers without changing their API.

    A context-local connection keeps unrelated sessions on their normal engine.
    No SAVEPOINT is used: SQLite must retain the real outer transaction until
    all handler calls have succeeded.
    """
    if _session_bind.get() is not None:
        raise RuntimeError("Nested service transactions are unsupported")
    with engine.begin() as connection:
        token = _session_bind.set(connection)
        try:
            yield connection
        finally:
            _session_bind.reset(token)
