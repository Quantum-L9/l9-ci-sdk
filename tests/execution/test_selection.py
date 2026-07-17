from pathlib import Path
from l9_ci.capabilities import RepositoryCapabilities
from l9_ci.execution import get_execution_profile, select_providers
from l9_ci.providers import ProviderRegistry, SemgrepProvider


def test_import_profile_selects_candidate(tmp_path: Path) -> None:
    registry = ProviderRegistry()
    registry.register(SemgrepProvider())
    caps = RepositoryCapabilities(".", ("python",), (), (), ("semgrep",))
    selected = select_providers(
        registry=registry,
        capabilities=caps,
        profile=get_execution_profile("import_only"),
        repository_root=tmp_path,
    )
    assert [provider.metadata.provider_id for provider in selected] == ["semgrep"]
