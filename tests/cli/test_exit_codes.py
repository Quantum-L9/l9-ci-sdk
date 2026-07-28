from l9_ci.cli import ExitCode


def test_exit_codes_are_stable() -> None:
    assert int(ExitCode.SUCCESS) == 0
    assert int(ExitCode.OPERATIONAL_LIMIT_EXCEEDED) == 9
