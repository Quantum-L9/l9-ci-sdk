from l9_ci.execution import ExecutionProfileName, get_execution_profile


def test_import_only_profile() -> None:
    profile = get_execution_profile("import_only")
    assert profile.name is ExecutionProfileName.IMPORT_ONLY
    assert profile.import_reports
