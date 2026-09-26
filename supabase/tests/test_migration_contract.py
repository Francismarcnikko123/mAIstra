from pathlib import Path


MIGRATIONS_DIR = Path(__file__).resolve().parents[1] / "migrations"
MIGRATION_SQL = "\n".join(
    path.read_text(encoding="utf-8").lower()
    for path in sorted(MIGRATIONS_DIR.glob("*.sql"))
)
DATABASE_CONTRACT_SQL = (
    Path(__file__).resolve().parent / "database" / "schema_contract.test.sql"
).read_text(encoding="utf-8").lower()


def test_questions_have_the_application_question_type_contract():
    assert "add column if not exists question_type text" in MIGRATION_SQL
    assert "alter column question_type set default 'program'" in MIGRATION_SQL
    assert "alter column question_type set not null" in MIGRATION_SQL
    assert "question_type in ('function', 'program')" in MIGRATION_SQL


def test_submissions_have_topic_and_question_columns():
    assert "add column if not exists topic text" in MIGRATION_SQL
    assert "add column if not exists question_id uuid" in MIGRATION_SQL


def test_submission_question_relationship_is_declared_and_indexed():
    assert "foreign key (question_id)" in MIGRATION_SQL
    assert "references public.questions (id)" in MIGRATION_SQL
    assert "on delete set null" in MIGRATION_SQL
    assert "on public.submissions (question_id)" in MIGRATION_SQL


def test_submissions_have_persisted_grade_columns():
    assert "add column if not exists grading_results jsonb" in MIGRATION_SQL
    assert "add column if not exists passed_test_cases integer" in MIGRATION_SQL
    assert "add column if not exists total_test_cases integer" in MIGRATION_SQL
    assert "add column if not exists graded_at timestamptz" in MIGRATION_SQL


def test_score_percentage_is_generated_from_test_case_counts():
    assert "score_percent numeric(5, 2)" in MIGRATION_SQL
    assert "generated always as" in MIGRATION_SQL
    assert "passed_test_cases::numeric * 100" in MIGRATION_SQL
    assert "total_test_cases" in MIGRATION_SQL


def test_persisted_grade_counts_are_consistent():
    assert "passed_test_cases >= 0" in MIGRATION_SQL
    assert "total_test_cases > 0" in MIGRATION_SQL
    assert "passed_test_cases <= total_test_cases" in MIGRATION_SQL


def test_persisted_input_changes_invalidate_the_grade_revision():
    assert (
        "add column if not exists grading_revision bigint default 0 not null"
        in MIGRATION_SQL
    )
    assert "create or replace function public.invalidate_submission_grade" in MIGRATION_SQL
    assert "before update of question_id, verified_text" in MIGRATION_SQL
    assert "new.grading_revision = old.grading_revision + 1" in MIGRATION_SQL


def test_successful_grade_writes_advance_revision_without_double_incrementing():
    assert "create or replace function public.advance_grading_revision_on_grade" in MIGRATION_SQL
    assert "advance_grading_revision_on_grade" in MIGRATION_SQL
    assert "before update of grading_results, passed_test_cases, total_test_cases, graded_at" in MIGRATION_SQL
    assert "before update of grading_results, passed_test_cases, total_test_cases, graded_at, status" not in MIGRATION_SQL
    assert "old.question_id is not distinct from new.question_id" in MIGRATION_SQL
    assert "old.verified_text is not distinct from new.verified_text" in MIGRATION_SQL
    assert "new.grading_revision = old.grading_revision + 1" in MIGRATION_SQL


def test_identical_code_resave_preserves_the_existing_graded_snapshot():
    assert "create or replace function public.invalidate_submission_grade" in MIGRATION_SQL
    assert "elsif old.status = 'graded' and new.status = 'verified'" in MIGRATION_SQL
    assert "new.status = old.status" in MIGRATION_SQL


def test_anon_grade_contract_covers_fresh_and_stale_compare_and_set_writes():
    assert "set local role anon" in DATABASE_CONTRACT_SQL
    assert "returning grading_revision" in DATABASE_CONTRACT_SQL
    assert "anon can save a grade and receive the atomically incremented revision" in DATABASE_CONTRACT_SQL
    assert "anon stale compare-and-set grade writes affect zero rows" in DATABASE_CONTRACT_SQL


def test_grades_are_saved_only_for_the_stored_code():
    assert "create or replace function public.save_submission_grade(" in MIGRATION_SQL
    assert "and verified_text = p_graded_code" in MIGRATION_SQL
    assert "and grading_revision = p_grading_revision" in MIGRATION_SQL
    assert "security invoker" in MIGRATION_SQL
    assert (
        "grant execute on function public.save_submission_grade(uuid, bigint, uuid, text, jsonb)"
        in MIGRATION_SQL
    )
    assert "public.save_submission_grade(" in DATABASE_CONTRACT_SQL


def test_submissions_record_the_mobile_gate_verdict():
    assert "add column if not exists gate_result text" in MIGRATION_SQL
    assert "gate_result in ('pass', 'fixable', 'retake')" in MIGRATION_SQL
    assert "alter policy submissions_public_insert" in MIGRATION_SQL
    assert "gate_result is null or gate_result in ('pass', 'fixable')" in MIGRATION_SQL
    assert "grant insert (gate_result) on table public.submissions" in MIGRATION_SQL


def test_questions_have_a_validated_flag_for_the_mobile_picker():
    assert (
        "add column if not exists can_publish boolean not null default false"
        in MIGRATION_SQL
    )
    assert "grant insert (can_publish) on table public.questions" in MIGRATION_SQL


def test_questions_can_be_edited_without_leaving_stale_grades():
    assert "create policy questions_public_update" in MIGRATION_SQL
    assert "can_publish\n) on table public.questions to anon, authenticated" in MIGRATION_SQL
    assert "create or replace function public.invalidate_grades_for_question" in MIGRATION_SQL
    assert "after update of test_cases, question_type" in MIGRATION_SQL
    assert "grading_revision = grading_revision + 1" in MIGRATION_SQL
