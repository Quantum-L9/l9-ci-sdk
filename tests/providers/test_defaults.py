from l9_ci.providers import ProviderRegistry, build_default_registry


def test_default_registry_contains_builtin_providers() -> None:
    registry = build_default_registry()
    assert isinstance(registry, ProviderRegistry)
    assert registry.provider_ids() == ("semgrep",)


def test_default_registry_returns_independent_instances() -> None:
    first = build_default_registry()
    second = build_default_registry()
    assert first is not second
    # Mutating one registry must not affect a freshly built one.
    first.unregister("semgrep")
    assert first.provider_ids() == ()
    assert second.provider_ids() == ("semgrep",)
