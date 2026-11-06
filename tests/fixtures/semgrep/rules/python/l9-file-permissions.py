# Regression fixture for l9_ci/rulesets/semgrep/python/l9-file-permissions.yml
# (L9-PYTHON-WRITABLE-FILE-MODE,
# l9.baseline.python.group-or-other-writable-file-mode).
#
# Run with: semgrep --test --config l9_ci/rulesets/semgrep/python \
#               tests/fixtures/semgrep/rules/python
# (tests/rulesets/test_semgrep_rule_fixtures.py does exactly this.)
#
# The criterion is group/other WRITE permission (operator decision
# 2026-11-06). Lines annotated ruleid grant it and MUST be reported; lines
# annotated ok do not, including the owner-only 0o700 that the community
# registry rule blocked on Quantum-L9/Enrichment.Inference.Engine at 12d8b351.
# Scan INPUT only, never imported, and listed in .semgrepignore.
# ruff: noqa
# type: ignore
import os
import pathlib
import stat
from stat import S_IRWXU, S_IWOTH

MODE_OWNER_ONLY = 0o700
MODE_WORLD_WRITABLE = 0o666


def owner_writable_modes_are_allowed(p, fd, path: pathlib.Path):
    # ok: l9.baseline.python.group-or-other-writable-file-mode
    os.chmod(p, 0o600)
    # ok: l9.baseline.python.group-or-other-writable-file-mode
    os.chmod(p, 0o700)
    # EIE app/services/domain_spec_workflow.py: restore owner-only on failure.
    # ok: l9.baseline.python.group-or-other-writable-file-mode
    os.fchmod(fd, 0o700)
    # ok: l9.baseline.python.group-or-other-writable-file-mode
    os.chmod(p, 0o644)
    # ok: l9.baseline.python.group-or-other-writable-file-mode
    os.chmod(p, 0o640)
    # Group/other EXECUTE is allowed by the operator decision.
    # ok: l9.baseline.python.group-or-other-writable-file-mode
    os.chmod(p, 0o750)
    # ok: l9.baseline.python.group-or-other-writable-file-mode
    os.chmod(p, 0o755)
    # ok: l9.baseline.python.group-or-other-writable-file-mode
    path.chmod(0o755)
    # ok: l9.baseline.python.group-or-other-writable-file-mode
    os.chmod(p, MODE_OWNER_ONLY)


def symbolic_and_mixed_without_write(p, st):
    # ok: l9.baseline.python.group-or-other-writable-file-mode
    os.chmod(p, stat.S_IRWXU)
    # 0o750, symbolically.
    # ok: l9.baseline.python.group-or-other-writable-file-mode
    os.chmod(p, stat.S_IRWXU | stat.S_IRGRP | stat.S_IXGRP)
    # Clearing write permission is the safe direction.
    # ok: l9.baseline.python.group-or-other-writable-file-mode
    os.chmod(p, st.st_mode & ~stat.S_IWOTH)
    # ok: l9.baseline.python.group-or-other-writable-file-mode
    os.chmod(p, st.st_mode & ~(stat.S_IWGRP | stat.S_IWOTH))
    # ok: l9.baseline.python.group-or-other-writable-file-mode
    os.chmod(p, st.st_mode & ~0o022)
    # A mask only keeps bits that are already there.
    # ok: l9.baseline.python.group-or-other-writable-file-mode
    os.chmod(p, st.st_mode & 0o777)


def not_a_permission_setting_call(p, mode):
    # A mode that cannot be evaluated is not reported (nor by the registry rule).
    # ok: l9.baseline.python.group-or-other-writable-file-mode
    os.chmod(p, mode)
    # Creation modes are masked by the umask; not a chmod.
    # ok: l9.baseline.python.group-or-other-writable-file-mode
    os.makedirs(p, 0o777)
    # ok: l9.baseline.python.group-or-other-writable-file-mode
    print(p, 0o777)


def numeric_write_grants_must_block(p, fd, path: pathlib.Path):
    # ruleid: l9.baseline.python.group-or-other-writable-file-mode
    os.chmod(p, 0o660)
    # ruleid: l9.baseline.python.group-or-other-writable-file-mode
    os.chmod(p, 0o666)
    # ruleid: l9.baseline.python.group-or-other-writable-file-mode
    os.chmod(p, 0o777)
    # Group write only.
    # ruleid: l9.baseline.python.group-or-other-writable-file-mode
    os.chmod(p, 0o620)
    # Other write only.
    # ruleid: l9.baseline.python.group-or-other-writable-file-mode
    os.chmod(p, 0o602)
    # A full st_mode value with the file-type bits.
    # ruleid: l9.baseline.python.group-or-other-writable-file-mode
    os.chmod(p, 0o100666)
    # 0o666 in decimal.
    # ruleid: l9.baseline.python.group-or-other-writable-file-mode
    os.chmod(p, 438)
    # A module constant.
    # ruleid: l9.baseline.python.group-or-other-writable-file-mode
    os.chmod(p, MODE_WORLD_WRITABLE)
    # ruleid: l9.baseline.python.group-or-other-writable-file-mode
    os.chmod(p, mode=0o777)
    # ruleid: l9.baseline.python.group-or-other-writable-file-mode
    os.chmod(p, 0o777, follow_symlinks=False)
    # ruleid: l9.baseline.python.group-or-other-writable-file-mode
    os.lchmod(p, 0o666)
    # ruleid: l9.baseline.python.group-or-other-writable-file-mode
    os.fchmod(fd, 0o666)
    # ruleid: l9.baseline.python.group-or-other-writable-file-mode
    path.chmod(0o777)


def symbolic_and_mixed_write_grants_must_block(p, st):
    # ruleid: l9.baseline.python.group-or-other-writable-file-mode
    os.chmod(p, stat.S_IRWXU | stat.S_IWOTH)
    # ruleid: l9.baseline.python.group-or-other-writable-file-mode
    os.chmod(p, S_IRWXU | S_IWOTH)
    # ruleid: l9.baseline.python.group-or-other-writable-file-mode
    os.chmod(p, stat.S_IRWXU | stat.S_IRWXG)
    # ruleid: l9.baseline.python.group-or-other-writable-file-mode
    os.chmod(p, stat.S_IRWXU | stat.S_IRWXO)
    # ruleid: l9.baseline.python.group-or-other-writable-file-mode
    os.chmod(p, st.st_mode | stat.S_IWGRP)
    # ruleid: l9.baseline.python.group-or-other-writable-file-mode
    os.chmod(p, stat.S_IMODE(st.st_mode) | stat.S_IWOTH)
    # Mixed symbolic and numeric.
    # ruleid: l9.baseline.python.group-or-other-writable-file-mode
    os.chmod(p, stat.S_IRWXU | 0o002)
    # ruleid: l9.baseline.python.group-or-other-writable-file-mode
    os.chmod(p, st.st_mode | 0o020)
