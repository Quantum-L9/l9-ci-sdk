import argparse
from pathlib import Path

from l9_ci.cli.exit_codes import ExitCode
from l9_ci.commands.manifest import _handle_check, _handle_generate


def _args(root: Path) -> argparse.Namespace:
    return argparse.Namespace(
        repository_root=str(root),
        output="MANIFEST.md",
        tracked_only=False,
        exclude_path=None,
        exclude_dir=None,
    )


def test_generate_writes_manifest(tmp_path: Path) -> None:
    (tmp_path / "file.py").write_text("", encoding="utf-8")

    result = _handle_generate(_args(tmp_path))

    assert result == int(ExitCode.SUCCESS)
    assert (tmp_path / "MANIFEST.md").exists()


def test_check_reports_drift_then_converges(tmp_path: Path) -> None:
    (tmp_path / "file.py").write_text("", encoding="utf-8")

    assert _handle_check(_args(tmp_path)) == int(ExitCode.GATE_FAILURE)
    assert _handle_check(_args(tmp_path)) == int(ExitCode.SUCCESS)
