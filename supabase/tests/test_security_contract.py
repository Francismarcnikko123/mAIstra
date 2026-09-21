import base64
import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
WEB_ENVIRONMENT = ROOT / "maistra_web" / "src" / "environment.ts"
MOBILE_MAIN = ROOT / "maistra_mobile" / "lib" / "main.dart"
SECURITY_MIGRATION = (
    ROOT
    / "supabase"
    / "migrations"
    / "20260921000000_lock_down_public_api.sql"
)


def _extract_quoted_value(source: str, field_name: str) -> str:
    match = re.search(rf"{field_name}\s*:\s*['\"]([^'\"]+)['\"]", source)
    assert match, f"{field_name} is missing"
    return match.group(1)


def _jwt_role(value: str) -> str | None:
    parts = value.split(".")
    if len(parts) != 3:
        return None
    payload = parts[1] + "=" * (-len(parts[1]) % 4)
    return json.loads(base64.urlsafe_b64decode(payload))["role"]


def test_browser_uses_a_publishable_key_not_a_service_role_key():
    source = WEB_ENVIRONMENT.read_text(encoding="utf-8")
    key = _extract_quoted_value(source, "supabaseKey")

    assert key.startswith("sb_publishable_")
    assert _jwt_role(key) != "service_role"


def test_mobile_uses_a_publishable_key_not_a_legacy_anon_key():
    source = MOBILE_MAIN.read_text(encoding="utf-8")
    key = _extract_quoted_value(source, "anonKey")

    assert key.startswith("sb_publishable_")
    assert _jwt_role(key) is None


def test_forward_security_migration_enforces_least_privilege():
    sql = SECURITY_MIGRATION.read_text(encoding="utf-8").lower()

    assert "alter table public.questions enable row level security" in sql
    assert "alter table public.submissions enable row level security" in sql
    assert "revoke all on table public.questions from anon, authenticated" in sql
    assert "revoke all on table public.submissions from anon, authenticated" in sql
    assert "grant select on table public.questions to anon, authenticated" in sql
    assert "grant select on table public.submissions to anon, authenticated" in sql
    assert "grant update (" in sql
    assert "grading_results" in sql
    assert "passed_test_cases" in sql
    assert "total_test_cases" in sql
    assert "graded_at" in sql
    assert "drop policy if exists \"allow public inserts\"" in sql
    assert "drop policy if exists \"allow public inserts questions\"" in sql
    assert "status = any (array[" in sql
    assert "'pending'::text" in sql
    assert "'verified'::text" in sql
    assert "'graded'::text" in sql


def test_forward_security_migration_limits_handwritten_uploads():
    sql = SECURITY_MIGRATION.read_text(encoding="utf-8").lower()

    assert "update storage.buckets" in sql
    assert "file_size_limit" in sql
    assert "allowed_mime_types" in sql
    assert "on storage.objects" in sql
    assert "bucket_id = 'handwritten-submissions'" in sql
