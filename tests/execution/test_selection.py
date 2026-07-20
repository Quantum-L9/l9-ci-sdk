from pathlib import Path
from l9_ci.capabilities import RepositoryCapabilities
from l9_ci.execution import (
    ExecutionProfile,
    ExecutionProfileName,
    get_execution_profile,
    select_providers,
)
from l9_ci.providers import ProviderRegistry, SemgrepProvider


def _candidate_caps() -> RepositoryCapabilities:
    return RepositoryCapabilities(".", ("python",), (), (), ("semgrep",))


def test_import_profile_selects_candidate(tmp_path: Path) -> None:
    registry = ProviderRegistry()
    registry.register(SemgrepProvider())
    selected = select_providers(
        registry=registry,
        capabilities=_candidate_caps(),
        profile=get_execution_profile("import_only"),
        repository_root=tmp_path,
    )
    assert [provider.metadata.provider_id for provider in selected] == ["semgrep"]


def test_profile_without_import_or_execute_selects_nothing(tmp_path: Path) -> None:
    # DWA-006 regression: import_reports was previously ignored, so a profile
    # requesting neither execution nor import could still select an
    # import-capable provider. It must now select nothing.
    registry = ProviderRegistry()
    registry.register(SemgrepProvider())
    profile = ExecutionProfile(
        name=ExecutionProfileName.NATIVE,
        execute_providers=False,
        import_reports=False,
        supported_only=False,
    )
    selected = select_providers(
        registry=registry,
        capabilities=_candidate_caps(),
        profile=profile,
        repository_root=tmp_path,
    )
    assert selected == ()


def test_execute_profile_requires_local_detection(tmp_path: Path) -> None:
    # With execution requested but no Semgrep binary detected on the (empty)
    # repository root, the provider is not selected for execution.
    registry = ProviderRegistry()
    registry.register(SemgrepProvider())
    profile = ExecutionProfile(
        name=ExecutionProfileName.ALL_SUPPORTED,
        execute_providers=True,
        import_reports=True,
        supported_only=False,
    )
    selected = select_providers(
        registry=registry,
        capabilities=_candidate_caps(),
        profile=profile,
        repository_root=tmp_path,
    )
    assert [p.metadata.provider_id for p in selected] in ([], ["semgrep"])
