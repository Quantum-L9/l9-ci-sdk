"""`l9.repository-metadata` must observe the repository, not be told about it.

Second of the two controls whose producers were missing but whose underlying
check already existed. `L9.CI.REPOSITORY_METADATA` returned
CONTROL_CARDINALITY_VIOLATION on every Assurance evaluation because nothing
emitted the check id, while `l9-ci manifest check` had all along been
performing exactly the comparison the control describes.

Two things make this a real producer rather than a populated field:

- The verdict is derived. `build_repository_manifest` re-derives the inventory
  from repository truth and it is compared against the committed manifest.
  There is no status parameter.
- The subject binding is derived too, which the sdk-validation projector
  cannot manage: `inspect_git_repository` reads the real HEAD, so `revision` is
  checked against the repository rather than trusted.
"""

from __future__ import annotations

import hashlib
import inspect
import json
import subprocess
from pathlib import Path

import pytest

from l9_ci.commands.observations import project_repository_metadata_observation
from l9_ci.integration import validate_observation

DIGEST = "c" * 64
STARTED = "2026-09-06T05:00:00Z"
COMPLETED = "2026-09-06T05:00:01Z"

COMMON = dict(
    repository="Quantum-L9/example",
    configuration_digest=DIGEST,
    run_id="77002",
    attempt=1,
    started_at=STARTED,
    completed_at=COMPLETED,
)


def _git(root: Path, *arguments: str) -> str:
    return subprocess.run(
        ["git", *arguments],
        cwd=root,
        capture_output=True,
        text=True,
        check=True,
        env={
            "GIT_AUTHOR_NAME": "t",
            "GIT_AUTHOR_EMAIL": "t@example.com",
            "GIT_COMMITTER_NAME": "t",
            "GIT_COMMITTER_EMAIL": "t@example.com",
            "GIT_CONFIG_GLOBAL": "/dev/null",
            "GIT_CONFIG_SYSTEM": "/dev/null",
            "HOME": str(root),
            "PATH": "/usr/bin:/bin:/usr/local/bin",
        },
    ).stdout


@pytest.fixture
def repository(tmp_path: Path) -> tuple[Path, str]:
    """A real git repository whose committed manifest reconciles.

    Built with git rather than mocked: the projector's whole claim is that it
    reads repository truth, and a fake would prove the opposite.
    """
    root = tmp_path / "repo"
    root.mkdir()
    _git(root, "init", "-q", "-b", "main")
    (root / "src").mkdir()
    (root / "src" / "example.py").write_text("x = 1\n", encoding="utf-8")
    (root / "README.md").write_text("# example\n", encoding="utf-8")

    # Commit first: `build_repository_manifest` inspects git, so it needs a
    # HEAD to exist before it can enumerate anything.
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "initial")

    # The manifest excludes itself, so its content is derivable before it
    # exists -- which is what lets a repository commit a reconciled one.
    from l9_ci.repository.manifest import build_repository_manifest

    manifest = build_repository_manifest(root, manifest_path=root / "MANIFEST.md")
    (root / "MANIFEST.md").write_text(manifest.render_markdown(), encoding="utf-8")

    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "add the reconciled manifest")
    revision = _git(root, "rev-parse", "HEAD").strip()
    return root, revision


class TestTheVerdictIsObservedNotAsserted:
    def test_the_projector_takes_no_status_parameter(self) -> None:
        parameters = inspect.signature(
            project_repository_metadata_observation
        ).parameters
        assert "status" not in parameters
        for forbidden in ("passed", "valid", "reconciled", "changed", "ok"):
            assert forbidden not in parameters

    def test_a_reconciled_manifest_is_observed_as_passed(
        self, repository: tuple[Path, str]
    ) -> None:
        root, revision = repository
        observation = project_repository_metadata_observation(
            repository_root=root, revision=revision, **COMMON
        )
        validate_observation(observation)
        assert observation["check"]["id"] == "l9.repository-metadata"
        assert observation["execution"]["status"] == "passed"

    def test_a_stale_manifest_is_observed_as_failed(
        self, repository: tuple[Path, str]
    ) -> None:
        """The real failure mode: a tracked file the manifest does not list.

        This is the same drift `l9-ci manifest check` turns into a non-zero
        exit, now visible to Assurance as evidence.
        """
        root, _revision = repository
        (root / "src" / "added.py").write_text("y = 2\n", encoding="utf-8")
        _git(root, "add", "-A")
        _git(root, "commit", "-q", "-m", "add a file without regenerating")
        revision = _git(root, "rev-parse", "HEAD").strip()

        observation = project_repository_metadata_observation(
            repository_root=root, revision=revision, **COMMON
        )
        validate_observation(observation)
        assert observation["execution"]["status"] == "failed"

    def test_a_missing_manifest_is_observed_as_failed(
        self, repository: tuple[Path, str]
    ) -> None:
        root, _revision = repository
        (root / "MANIFEST.md").unlink()
        _git(root, "add", "-A")
        _git(root, "commit", "-q", "-m", "drop the manifest")
        revision = _git(root, "rev-parse", "HEAD").strip()

        observation = project_repository_metadata_observation(
            repository_root=root, revision=revision, **COMMON
        )
        assert observation["execution"]["status"] == "failed"

    def test_it_does_not_write_the_manifest_it_is_describing(
        self, repository: tuple[Path, str]
    ) -> None:
        """A producer of evidence must not mutate its own subject.

        `manifest check` reconciles by *writing*; this must not, or the second
        run would observe a repository the first run changed.
        """
        root, _revision = repository
        (root / "src" / "added.py").write_text("y = 2\n", encoding="utf-8")
        _git(root, "add", "-A")
        _git(root, "commit", "-q", "-m", "drift")
        revision = _git(root, "rev-parse", "HEAD").strip()

        before = (root / "MANIFEST.md").read_bytes()
        first = project_repository_metadata_observation(
            repository_root=root, revision=revision, **COMMON
        )
        assert (root / "MANIFEST.md").read_bytes() == before
        assert _git(root, "status", "--porcelain").strip() == ""

        second = project_repository_metadata_observation(
            repository_root=root, revision=revision, **COMMON
        )
        assert first == second
        assert second["execution"]["status"] == "failed"


class TestIdentityIsObserved:
    def test_a_revision_that_disagrees_with_head_raises(
        self, repository: tuple[Path, str]
    ) -> None:
        root, _revision = repository
        with pytest.raises(ValueError, match="does not match the repository HEAD"):
            project_repository_metadata_observation(
                repository_root=root, revision="b" * 40, **COMMON
            )

    def test_a_non_git_root_raises_rather_than_trusting_the_caller(
        self, tmp_path: Path
    ) -> None:
        """No observable revision means no honest subject binding."""
        plain = tmp_path / "not-a-repo"
        plain.mkdir()
        with pytest.raises(ValueError, match="not a git repository"):
            project_repository_metadata_observation(
                repository_root=plain, revision="a" * 40, **COMMON
            )

    def test_a_dirty_tree_raises(self, repository: tuple[Path, str]) -> None:
        """The control declares exactRevision; a dirty tree is not that revision."""
        root, revision = repository
        (root / "src" / "example.py").write_text("x = 999\n", encoding="utf-8")
        with pytest.raises(ValueError, match="working tree is dirty"):
            project_repository_metadata_observation(
                repository_root=root, revision=revision, **COMMON
            )

    def test_an_empty_revision_raises(self, repository: tuple[Path, str]) -> None:
        root, _revision = repository
        with pytest.raises(ValueError, match="revision is required"):
            project_repository_metadata_observation(
                repository_root=root, revision="  ", **COMMON
            )

    def test_repository_revision_and_run_survive_the_projection(
        self, repository: tuple[Path, str]
    ) -> None:
        root, revision = repository
        observation = project_repository_metadata_observation(
            repository_root=root, revision=revision, **COMMON
        )
        assert observation["subject"]["repository"] == {
            "host": "github.com",
            "owner": "Quantum-L9",
            "name": "example",
        }
        assert observation["subject"]["revision"]["commit"] == revision
        assert observation["execution"]["runId"] == "77002"
        assert observation["execution"]["attempt"] == 1


class TestTheObservationIsWellFormed:
    def test_it_is_deterministic(self, repository: tuple[Path, str]) -> None:
        root, revision = repository
        first = project_repository_metadata_observation(
            repository_root=root, revision=revision, **COMMON
        )
        second = project_repository_metadata_observation(
            repository_root=root, revision=revision, **COMMON
        )
        assert first == second
        assert first["observationId"] == second["observationId"]

    def test_the_artifact_addresses_the_derived_manifest(
        self, repository: tuple[Path, str]
    ) -> None:
        root, revision = repository
        observation = project_repository_metadata_observation(
            repository_root=root, revision=revision, **COMMON
        )
        artifact = observation["artifacts"][0]
        expected = hashlib.sha256((root / "MANIFEST.md").read_bytes()).hexdigest()
        assert artifact["digest"] == {"algorithm": "sha256", "value": expected}
        assert artifact["name"] == "repository-manifest"

    def test_the_artifact_path_is_repository_relative(
        self, repository: tuple[Path, str]
    ) -> None:
        """An absolute path would leak the runner's layout into evidence."""
        root, revision = repository
        observation = project_repository_metadata_observation(
            repository_root=root, revision=revision, **COMMON
        )
        path = observation["artifacts"][0]["path"]
        assert path == "MANIFEST.md"
        assert not Path(path).is_absolute()
        assert str(root) not in json.dumps(observation)

    def test_it_carries_no_findings_and_zero_counts(
        self, repository: tuple[Path, str]
    ) -> None:
        root, revision = repository
        observation = project_repository_metadata_observation(
            repository_root=root, revision=revision, **COMMON
        )
        assert observation["findings"] == []
        assert observation["summary"] == {
            "findingCount": 0,
            "errorCount": 0,
            "warningCount": 0,
            "informationalCount": 0,
        }

    def test_the_producer_is_the_running_sdk(
        self, repository: tuple[Path, str]
    ) -> None:
        from l9_ci import __version__

        root, revision = repository
        observation = project_repository_metadata_observation(
            repository_root=root, revision=revision, **COMMON
        )
        assert observation["producer"]["version"] == __version__
        assert observation["producer"]["id"] == "l9-ci-sdk"

    def test_a_mutated_observation_fails_validation(
        self, repository: tuple[Path, str]
    ) -> None:
        """Fail-closed downstream: observationId is a content address."""
        root, revision = repository
        observation = project_repository_metadata_observation(
            repository_root=root, revision=revision, **COMMON
        )
        observation["execution"]["status"] = "failed"
        with pytest.raises(ValueError, match="does not match the content address"):
            validate_observation(observation)


class TestOnlyCheckFailuresBecomeFailedObservations:
    def test_an_internal_defect_propagates_rather_than_becoming_failed(
        self, repository: tuple[Path, str], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Same boundary as the sdk-validation projector.

        A crash in the manifest builder must not be reported as a repository
        whose metadata is invalid.
        """
        from l9_ci.commands import observations

        def exploding_builder(*_args: object, **_kwargs: object) -> object:
            raise AttributeError("a refactor broke the manifest builder")

        monkeypatch.setattr(
            observations, "build_repository_manifest", exploding_builder
        )
        root, revision = repository
        with pytest.raises(AttributeError, match="broke the manifest builder"):
            project_repository_metadata_observation(
                repository_root=root, revision=revision, **COMMON
            )

    def test_a_builder_rejection_still_becomes_failed(
        self, repository: tuple[Path, str], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from l9_ci.commands import observations

        def rejecting_builder(*_args: object, **_kwargs: object) -> object:
            raise ValueError("repository enumeration failed")

        monkeypatch.setattr(
            observations, "build_repository_manifest", rejecting_builder
        )
        root, revision = repository
        observation = project_repository_metadata_observation(
            repository_root=root, revision=revision, **COMMON
        )
        assert observation["execution"]["status"] == "failed"
