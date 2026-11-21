"""Framework-scoped registry rules apply only where the framework is used.

CTO, 2026-11-21: a Django rule fired on Cursor-Governance
``environment/agents/generated-data/invalidation/repository_event_bridge.py:279``
and on this SDK's ``l9_ci/providers/semgrep/provider.py:153``, although neither
is a Django project. The Django ``subprocess-injection`` rule treats any
parameter named ``request`` as an HTTP request. Its findings are now withheld
where Django is not detected: the evidence is kept and the bundle says why.
No waiver is involved.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from l9_ci.artifacts import load_and_validate_bundle
from l9_ci.capabilities import detect_django
from l9_ci.gates import GateStatus, evaluate_gate
from l9_ci.pipeline import SemgrepPipelineRequest, run_semgrep_pipeline

REPORT = Path("tests/fixtures/semgrep/report-sdk-provider-subprocess-injection.json")
RULE = (
    "python.django.security.injection.command.subprocess-injection.subprocess-injection"
)


def _tree(root: Path, files: dict[str, str]) -> Path:
    for relative, content in files.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    return root


@pytest.mark.parametrize(
    ("files", "evidence"),
    [
        ({"requirements.txt": "Django>=4.2\nrequests\n"}, ["requirements.txt"]),
        ({"requirements-prod.txt": "django[argon2]==5.0\n"}, ["requirements-prod.txt"]),
        (
            {"pyproject.toml": '[project]\ndependencies = ["django~=5.0", "x"]\n'},
            ["pyproject.toml"],
        ),
        (
            {"manage.py": "import os\nfrom django.core.management import x\n"},
            ["manage.py"],
        ),
        # Codex review on #141: a PEP 508 direct reference names Django too.
        (
            {"requirements.txt": "django @ https://example.invalid/django.tar.gz\n"},
            ["requirements.txt"],
        ),
        (
            {
                "pyproject.toml": '[project]\ndependencies = ["django@ git+https://x/y"]\n'
            },
            ["pyproject.toml"],
        ),
    ],
)
def test_django_is_detected_from_its_declaration(
    tmp_path: Path, files: dict[str, str], evidence: list[str]
) -> None:
    detection = detect_django(_tree(tmp_path / "repo", files))
    assert detection.detected is True
    assert list(detection.evidence) == evidence


@pytest.mark.parametrize(
    "files",
    [
        {"requirements.txt": "django-environ==0.11\nrequests\n"},
        {"pyproject.toml": '[project]\ndependencies = ["djangorestframework-stubs"]\n'},
        {"app/handler.py": "def view(request):\n    return request\n"},
        {"manage.py": "print('not a django entry point')\n"},
        {},
    ],
)
def test_django_is_not_detected_without_its_declaration(
    tmp_path: Path, files: dict[str, str]
) -> None:
    root = _tree(tmp_path / "repo", {"README.md": "x\n", **files})
    assert detect_django(root).detected is False


def test_an_unreadable_declaration_makes_detection_unknown(tmp_path: Path) -> None:
    """Codex review on #141: a file the SDK cannot read is not "no Django"."""
    root = _tree(tmp_path / "repo", {"README.md": "x\n"})
    outside = tmp_path / "outside.txt"
    outside.write_text("Django>=4.2\n", encoding="utf-8")
    (root / "requirements.txt").symlink_to(outside)
    detection = detect_django(root, ("README.md", "requirements.txt"))
    assert detection.detected is None
    assert detection.unreadable == ("requirements.txt",)


def test_an_oversized_declaration_makes_detection_unknown(tmp_path: Path) -> None:
    root = _tree(
        tmp_path / "repo", {"requirements.txt": "# pad\n" * 200_000 + "Django\n"}
    )
    assert detect_django(root, ("requirements.txt",)).detected is None


def test_evidence_elsewhere_outweighs_an_unreadable_file(tmp_path: Path) -> None:
    root = _tree(
        tmp_path / "repo",
        {"requirements.txt": "Django>=4.2\n", "setup.cfg": "# pad\n" * 200_000},
    )
    detection = detect_django(root, ("requirements.txt", "setup.cfg"))
    assert detection.detected is True
    assert detection.unreadable == ("setup.cfg",)


def _bundle(tmp_path: Path, detected: dict[str, bool | None] | None):  # type: ignore[no-untyped-def]
    output = tmp_path / "bundle.json"
    run_semgrep_pipeline(
        SemgrepPipelineRequest(
            report_path=REPORT,
            repository_root=Path(".").resolve(),
            snapshot_id="snapshot-1",
            SDK_version="2.0.0-test",
            output_path=output,
            provider_version="1.171.0",
            required=True,
            generated_at="2026-11-21T00:00:00Z",
            detected_frameworks=detected,
        )
    )
    return load_and_validate_bundle(output)


def test_a_django_rule_finding_is_withheld_where_django_is_not_used(
    tmp_path: Path,
) -> None:
    bundle = _bundle(tmp_path, {"django": False})
    assert bundle.findings == ()
    assert len(bundle.evidence) == 1  # the provider fact is kept
    (note,) = [item for item in bundle.limitations if item.startswith("framework rule")]
    assert RULE in note
    assert "django is not detected" in note
    assert "l9_ci/providers/semgrep/provider.py:153" in note
    assert evaluate_gate(bundle).status is GateStatus.PASS


def test_a_django_rule_finding_stands_in_a_django_project(tmp_path: Path) -> None:
    bundle = _bundle(tmp_path, {"django": True})
    (finding,) = bundle.findings
    assert finding.provider_rule_id == RULE


def test_unknown_framework_state_withholds_nothing(tmp_path: Path) -> None:
    """Known-good fail-safe: when detection could not run, every finding stays."""
    bundle = _bundle(tmp_path, None)
    assert len(bundle.findings) == 1


def test_an_unknown_detection_withholds_nothing(tmp_path: Path) -> None:
    """Known-good fail-safe: unknown for one framework keeps its findings."""
    bundle = _bundle(tmp_path, {"django": None})
    assert len(bundle.findings) == 1
    assert not [i for i in bundle.limitations if i.startswith("framework rule")]


def test_this_sdk_is_not_a_django_project() -> None:
    assert detect_django(Path(".")).detected is False
