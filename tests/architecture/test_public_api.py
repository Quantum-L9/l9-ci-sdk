from l9_ci import artifacts, contracts, providers


def test_contract_public_surface() -> None:
    expected = {
        "Confidence",
        "Coverage",
        "CoverageStatus",
        "EvidenceRecord",
        "Finding",
        "FindingBundle",
        "FindingClassification",
        "ProviderFailure",
        "ProviderFailureType",
        "ProviderRun",
        "ResolutionStatus",
        "RuleMode",
        "Severity",
        "SnapshotDescriptor",
        "SourceLocation",
    }
    assert expected.issubset(set(contracts.__all__))


def test_provider_public_surface() -> None:
    expected = {
        "Provider",
        "ProviderMetadata",
        "ProviderRegistry",
        "ProviderState",
        "ProviderExecutionRequest",
        "ProviderExecutionResult",
        "ProviderNormalizationContext",
        "ProviderNormalizationResult",
    }
    assert expected.issubset(set(providers.__all__))


def test_artifact_public_surface() -> None:
    expected = {
        "bundle_bytes",
        "check_bundle_compatibility",
        "load_and_validate_bundle",
        "validate_bundle",
        "write_bundle_atomic",
    }
    assert expected.issubset(set(artifacts.__all__))


def test_phase4_public_surfaces() -> None:
    from l9_ci import capabilities, cli, execution, gates, repository

    assert {"RepositorySnapshot", "build_repository_snapshot"}.issubset(
        repository.__all__
    )
    assert {"RepositoryCapabilities", "detect_repository_capabilities"}.issubset(
        capabilities.__all__
    )
    assert {"ExecutionProfile", "ExecutionProfileName", "select_providers"}.issubset(
        execution.__all__
    )
    assert {"GateResult", "GateStatus", "evaluate_gate"}.issubset(gates.__all__)
    assert {"Diagnostic", "ExitCode", "OutputFormat"}.issubset(cli.__all__)
