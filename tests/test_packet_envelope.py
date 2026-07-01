from pathlib import Path
from l9_ci.scanners.packet_envelope import scan


def test_packet_envelope_import_is_blocked(tmp_path: Path) -> None:
    f = tmp_path / "bad.py"
    f.write_text("from x import PacketEnvelope\n", encoding="utf-8")
    violations = scan([tmp_path], root=tmp_path)
    assert violations
    assert violations[0].code == "PE-001"


def test_transport_packet_is_allowed(tmp_path: Path) -> None:
    f = tmp_path / "good.py"
    f.write_text("from x import TransportPacket\n", encoding="utf-8")
    assert scan([tmp_path], root=tmp_path) == []


def test_packet_scanner_supports_exclude_suffix(tmp_path: Path) -> None:
    f = tmp_path / "generated" / "bad.py"
    f.parent.mkdir()
    f.write_text("from x import PacketEnvelope\n", encoding="utf-8")
    assert scan([tmp_path], root=tmp_path, exclude=["generated/bad.py"]) == []


def test_packetenvelope_inside_multiline_docstring_is_not_flagged(tmp_path: Path) -> None:
    # A reference inside a multi-line docstring body is prose, not a usage,
    # and must not produce a false positive.
    f = tmp_path / "doc.py"
    f.write_text(
        '"""Module notes.\n\nHistorically this used PacketEnvelope before TransportPacket.\n"""\n\nx = 1\n',
        encoding="utf-8",
    )
    assert scan([tmp_path], root=tmp_path) == []


def test_real_usage_after_docstring_is_still_flagged(tmp_path: Path) -> None:
    f = tmp_path / "mix.py"
    f.write_text(
        '"""Mentions PacketEnvelope in prose."""\nfrom x import PacketEnvelope\n',
        encoding="utf-8",
    )
    violations = scan([tmp_path], root=tmp_path)
    assert [v.code for v in violations] == ["PE-001"]
