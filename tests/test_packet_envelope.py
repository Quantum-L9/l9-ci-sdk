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
