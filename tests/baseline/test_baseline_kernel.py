"""Kernel tests: contracts, fingerprints, comparator outcomes, ledger loading."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest

from l9_ci.baseline import (
    BaselineEntry,
    ObservedFinding,
    TestQuarantineEntry,
    ViolationKind,
    compare,
    load_ledger,
    normalize_failure_text,
    scanner_finding_fingerprint,
    fingerprint_for_test_failure,
)
from l9_ci.baseline.packet_envelope import scan_repository
from l9_ci.baseline.pytest_adapter import parse_report_log

TODAY = date(2026, 7, 23)
FUTURE = "2026-12-31"
PAST = "2026-01-01"


def _fp(seed: str) -> str:
    return scanner_finding_fingerprint("rule-x", f"pkg/{seed}.py", f"name-ref:{seed}")


def _entry(seed: str, *, expires: str = FUTURE, **overrides) -> BaselineEntry:
    payload = dict(
        id=f"debt/{seed}",
        gate="gate/x",
        rule="rule-x",
        fingerprint=_fp(seed),
        path=f"pkg/{seed}.py",
        owner="@cryptoxdog",
        issue="Quantum-L9/Cognitive.Engine.Graphs#140",
        introduced_before="8fe08c5",
        expires=expires,
        removal_condition="finding-absent",
    )
    payload.update(overrides)
    return BaselineEntry(**payload)


def _observed(seed: str, *, fingerprint: str | None = None) -> ObservedFinding:
    return ObservedFinding(
        gate="gate/x",
        rule="rule-x",
        fingerprint=fingerprint or _fp(seed),
        path=f"pkg/{seed}.py",
        identity=f"rule-x::pkg/{seed}.py",
        message=f"finding {seed}",
    )


class TestFingerprints:
    def test_deterministic_across_calls(self) -> None:
        a = fingerprint_for_test_failure(
            "tests/test_x.py::test_a", "AssertionError", "boom"
        )
        b = fingerprint_for_test_failure(
            "tests/test_x.py::test_a", "AssertionError", "boom"
        )
        assert a == b and len(a) == 64

    def test_volatile_values_do_not_change_fingerprint(self) -> None:
        sig_one = "failed at 0x7f3a2b1c with /tmp/pytest-123/file at 2026-07-23T10:00:00Z, line 42"
        sig_two = "failed at 0x5e9d001a with /tmp/pytest-999/other at 2026-07-24T11:30:15Z, line 97"
        a = fingerprint_for_test_failure(
            "t::n", "RuntimeError", normalize_failure_text(sig_one)
        )
        b = fingerprint_for_test_failure(
            "t::n", "RuntimeError", normalize_failure_text(sig_two)
        )
        assert a == b

    def test_run_random_hex_ids_do_not_change_fingerprint(self) -> None:
        sig_one = (
            "ContractViolationError: ContractViolation"
            "[gs_8a1d37f6a143440eb2844cab0f824394]: content_hash mismatch: "
            "expected='ba582c36c79d949f8d56a8599b0a11faa671efcab3933c8b1eb867"
            "5379f9cc89' got='afcfe5aca59e4a544fc3152748ba9482f2241dbdfec607"
            "d690b1163a032150fd'"
        )
        sig_two = (
            "ContractViolationError: ContractViolation"
            "[gs_766c921b5be44092bbb742d98bd1f06e]: content_hash mismatch: "
            "expected='ba582c36c79d949f8d56a8599b0a11faa671efcab3933c8b1eb867"
            "5379f9cc89' got='049e16832f433963dfbc27c5e3bed0d1bca57062293c232"
            "165449e6bb5822f94'"
        )
        a = fingerprint_for_test_failure(
            "t::n", "ContractViolationError", normalize_failure_text(sig_one)
        )
        b = fingerprint_for_test_failure(
            "t::n", "ContractViolationError", normalize_failure_text(sig_two)
        )
        assert a == b

    def test_set_literal_order_does_not_change_fingerprint(self) -> None:
        # Set iteration order is hash-seed dependent, so the same
        # logical failure renders {'a', 'b'} or {'b', 'a'} per run.
        sig_one = (
            "Failed: T5-03: engine/x.py imports chassis \u2014 only "
            "{'handlers.py', 'boot.py'} may do this"
        )
        sig_two = (
            "Failed: T5-03: engine/x.py imports chassis \u2014 only "
            "{'boot.py', 'handlers.py'} may do this"
        )
        a = fingerprint_for_test_failure(
            "t::n", "Failed", normalize_failure_text(sig_one)
        )
        b = fingerprint_for_test_failure(
            "t::n", "Failed", normalize_failure_text(sig_two)
        )
        assert a == b

    def test_dict_reprs_are_not_reordered(self) -> None:
        # Dict reprs contain ':' and must not be rewritten; insertion
        # order in dicts is deterministic and meaningful.
        sig = "AssertionError: got {'b': 1, 'a': 2}"
        normalized = normalize_failure_text(sig)
        assert "{'b': 1, 'a': 2}" in normalized

    def test_component_boundaries_do_not_collide(self) -> None:
        assert scanner_finding_fingerprint(
            "ab", "c", "d"
        ) != scanner_finding_fingerprint("a", "bc", "d")

    def test_empty_components_rejected(self) -> None:
        with pytest.raises(ValueError):
            scanner_finding_fingerprint("", "path", "usage")


class TestSchemas:
    def test_placeholder_owner_rejected(self) -> None:
        with pytest.raises(ValueError, match="owner"):
            _entry("a", owner="TBD")

    def test_missing_issue_rejected(self) -> None:
        with pytest.raises(ValueError, match="issue"):
            _entry("a", issue="")

    def test_bad_removal_condition_rejected(self) -> None:
        with pytest.raises(ValueError, match="removal_condition"):
            _entry("a", removal_condition="someday maybe")

    def test_migrated_to_condition_accepted(self) -> None:
        entry = _entry("a", removal_condition="migrated-to:TransportPacket")
        assert entry.removal_condition.kind == "migrated-to"
        assert entry.removal_condition.target == "TransportPacket"


class TestComparatorOutcomes:
    def test_known_finding_tolerated(self) -> None:
        result = compare("gate/x", [_observed("a")], [_entry("a")], evaluated_on=TODAY)
        assert result.passed and result.summary.known_total == 1

    def test_new_finding_fails(self) -> None:
        result = compare(
            "gate/x", [_observed("zzz")], [_entry("a")], evaluated_on=TODAY
        )
        kinds = {violation.kind for violation in result.violations}
        assert not result.passed and ViolationKind.NEW_FINDING in kinds
        # The ledgered-but-absent entry also surfaces as stale.
        assert ViolationKind.STALE_ENTRY in kinds

    def test_changed_signature_fails(self) -> None:
        changed = _observed("a", fingerprint=_fp("a-changed"))
        result = compare("gate/x", [changed], [_entry("a")], evaluated_on=TODAY)
        assert not result.passed
        assert {v.kind for v in result.violations} == {ViolationKind.CHANGED_SIGNATURE}

    def test_increased_finding_fails(self) -> None:
        result = compare(
            "gate/x",
            [_observed("a"), _observed("a")],
            [_entry("a")],
            evaluated_on=TODAY,
        )
        assert not result.passed
        assert any(v.kind is ViolationKind.INCREASED_FINDING for v in result.violations)

    def test_expired_exception_fails_even_if_present(self) -> None:
        result = compare(
            "gate/x", [_observed("a")], [_entry("a", expires=PAST)], evaluated_on=TODAY
        )
        assert not result.passed
        assert any(v.kind is ViolationKind.EXPIRED_EXCEPTION for v in result.violations)

    def test_stale_entry_fails_when_finding_resolved(self) -> None:
        result = compare("gate/x", [], [_entry("a")], evaluated_on=TODAY)
        assert not result.passed
        assert result.suggested_removals == ("debt/a",)
        assert {v.kind for v in result.violations} == {ViolationKind.STALE_ENTRY}

    def test_resolved_not_removed_for_passing_quarantined_test(self) -> None:
        quarantine = TestQuarantineEntry(
            id="quarantine/test-a",
            test_node_id="tests/test_x.py::test_a",
            fingerprint=fingerprint_for_test_failure(
                "tests/test_x.py::test_a", "AssertionError", "boom"
            ),
            exception_type="AssertionError",
            failure_signature="boom",
            owner="@cryptoxdog",
            issue="Quantum-L9/Cognitive.Engine.Graphs#141",
            introduced_before="8fe08c5",
            expires=FUTURE,
            removal_condition="test-passes",
        )
        result = compare(
            "tests/pytest",
            [],
            [quarantine],
            evaluated_on=TODAY,
            passing_identities=["tests/test_x.py::test_a"],
        )
        assert not result.passed
        assert {v.kind for v in result.violations} == {
            ViolationKind.RESOLVED_NOT_REMOVED
        }

    def test_duplicate_fingerprint_is_malformed(self) -> None:
        result = compare(
            "gate/x",
            [_observed("a")],
            [_entry("a"), _entry("a", id="debt/a-duplicate")],
            evaluated_on=TODAY,
        )
        assert not result.passed
        assert any(
            v.kind is ViolationKind.MALFORMED_BASELINE for v in result.violations
        )

    def test_empty_ledger_and_no_findings_passes(self) -> None:
        result = compare("gate/x", [], [], evaluated_on=TODAY)
        assert result.passed and result.summary.violations_total == 0

    def test_deterministic_output_ordering(self) -> None:
        observed = [_observed("z"), _observed("m"), _observed("b")]
        first = compare("gate/x", observed, [], evaluated_on=TODAY)
        second = compare("gate/x", list(reversed(observed)), [], evaluated_on=TODAY)
        assert [v.to_dict() for v in first.violations] == [
            v.to_dict() for v in second.violations
        ]


class TestLedgerLoading:
    def _write(self, tmp_path: Path, body: str) -> Path:
        target = tmp_path / "ledger.yml"
        target.write_text(body, encoding="utf-8")
        return target

    def test_missing_owner_flagged_not_dropped(self, tmp_path: Path) -> None:
        ledger = self._write(
            tmp_path,
            f"""\
schema_version: "1.0.0"
gate: gate/x
entries:
  - id: debt/a
    gate: gate/x
    rule: rule-x
    fingerprint: "{_fp("a")}"
    path: pkg/a.py
    owner: ""
    issue: "Quantum-L9/Cognitive.Engine.Graphs#140"
    introduced_before: "8fe08c5"
    expires: "{FUTURE}"
    removal_condition: finding-absent
""",
        )
        loaded = load_ledger(ledger, entry_kind="baseline")
        assert len(loaded.entries) == 0
        assert any(v.kind is ViolationKind.MISSING_OWNER for v in loaded.violations)

    def test_unsupported_schema_version_flagged(self, tmp_path: Path) -> None:
        ledger = self._write(
            tmp_path, 'schema_version: "9.9.9"\ngate: gate/x\nentries: []\n'
        )
        loaded = load_ledger(ledger, entry_kind="baseline")
        assert any(
            v.kind is ViolationKind.MALFORMED_BASELINE for v in loaded.violations
        )

    def test_unparseable_yaml_raises(self, tmp_path: Path) -> None:
        ledger = self._write(tmp_path, "entries: [unclosed")
        with pytest.raises(ValueError):
            load_ledger(ledger, entry_kind="baseline")


class TestPytestAdapter:
    def _report(self, tmp_path: Path, records: list[dict]) -> Path:
        target = tmp_path / "report.jsonl"
        target.write_text(
            "\n".join(json.dumps(record) for record in records), encoding="utf-8"
        )
        return target

    def test_failure_error_skip_pass_distinguished(self, tmp_path: Path) -> None:
        records = [
            {
                "$report_type": "TestReport",
                "nodeid": "tests/test_a.py::test_fails",
                "when": "call",
                "outcome": "failed",
                "keywords": {},
                "longrepr": {
                    "reprcrash": {
                        "message": "AssertionError: expected 1 got 2",
                        "path": "/home/user/tests/test_a.py",
                        "lineno": 10,
                    }
                },
            },
            {
                "$report_type": "TestReport",
                "nodeid": "tests/test_a.py::test_setup_error",
                "when": "setup",
                "outcome": "failed",
                "keywords": {},
                "longrepr": {
                    "reprcrash": {
                        "message": "RuntimeError: fixture exploded",
                        "path": "x",
                        "lineno": 1,
                    }
                },
            },
            {
                "$report_type": "TestReport",
                "nodeid": "tests/test_a.py::test_skipped",
                "when": "call",
                "outcome": "skipped",
                "keywords": {},
                "longrepr": ["f.py", 1, "Skipped: not relevant"],
            },
            {
                "$report_type": "TestReport",
                "nodeid": "tests/test_a.py::test_passes",
                "when": "call",
                "outcome": "passed",
                "keywords": {},
            },
        ]
        result = parse_report_log(self._report(tmp_path, records))
        rules = {finding.identity: finding.rule for finding in result.findings}
        assert rules["tests/test_a.py::test_fails"] == "pytest-failure"
        assert rules["tests/test_a.py::test_setup_error"] == "pytest-error"
        assert result.passing_node_ids == ("tests/test_a.py::test_passes",)
        assert result.skipped_node_ids == ("tests/test_a.py::test_skipped",)

    def test_collection_error_reported(self, tmp_path: Path) -> None:
        records = [
            {
                "$report_type": "CollectReport",
                "nodeid": "tests/test_broken.py",
                "outcome": "failed",
                "longrepr": "ImportError: cannot import name 'gone'",
            }
        ]
        result = parse_report_log(self._report(tmp_path, records))
        assert len(result.findings) == 1
        assert result.findings[0].rule == "pytest-collection-failure"

    def test_line_number_change_keeps_fingerprint(self, tmp_path: Path) -> None:
        def record(lineno: int, path: str) -> dict:
            return {
                "$report_type": "TestReport",
                "nodeid": "tests/test_a.py::test_fails",
                "when": "call",
                "outcome": "failed",
                "keywords": {},
                "longrepr": {
                    "reprcrash": {
                        "message": f"AssertionError: assert 1 == 2, line {lineno}",
                        "path": path,
                        "lineno": lineno,
                    }
                },
            }

        first = parse_report_log(self._report(tmp_path, [record(10, "/home/aa/t.py")]))
        second = parse_report_log(self._report(tmp_path, [record(99, "/home/bb/t.py")]))
        assert first.findings[0].fingerprint == second.findings[0].fingerprint


class TestPacketEnvelopeScanner:
    def test_detects_all_usage_kinds_and_skips_comments(self, tmp_path: Path) -> None:
        (tmp_path / "pkg").mkdir()
        (tmp_path / "pkg" / "user.py").write_text(
            "from engine.transport import PacketEnvelope\n"
            "import engine.transport\n"
            "\n"
            "# PacketEnvelope in a comment is not debt\n"
            "\n"
            "def build(payload) -> PacketEnvelope:\n"
            '    other: "PacketEnvelope | None" = None\n'
            "    legacy = engine.transport.PacketEnvelope(payload)\n"
            "    return legacy\n",
            encoding="utf-8",
        )
        (tmp_path / "docs").mkdir()
        (tmp_path / "docs" / "notes.py").write_text(
            "PacketEnvelope = 'documentation example, excluded dir'\n",
            encoding="utf-8",
        )
        findings = scan_repository(tmp_path)
        paths = {finding.path for finding in findings}
        assert paths == {"pkg/user.py"}
        kinds = {finding.attributes["usage_kind"] for finding in findings}
        assert "import-from" in kinds
        assert "attr-ref" in kinds
        assert "name-ref" in kinds
        assert "string-annotation" in kinds

    def test_declaration_site_excluded(self, tmp_path: Path) -> None:
        (tmp_path / "envelope.py").write_text(
            "class PacketEnvelope:\n    pass\n", encoding="utf-8"
        )
        with_decl = scan_repository(tmp_path, declaration_paths=["envelope.py"])
        without_decl = scan_repository(tmp_path)
        assert with_decl == ()
        assert len(without_decl) == 1

    def test_scan_is_deterministic(self, tmp_path: Path) -> None:
        (tmp_path / "a.py").write_text("import PacketEnvelope\n", encoding="utf-8")
        first = scan_repository(tmp_path)
        second = scan_repository(tmp_path)
        assert [f.to_dict() for f in first] == [f.to_dict() for f in second]
