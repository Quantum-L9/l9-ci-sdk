from __future__ import annotations

import argparse
import sys
from pathlib import Path

from l9_ci.gate.ci_gate import evaluate, format_gate, parse_result_pairs
from l9_ci.governance.approval import (
    evaluate_governance_approval,
    format_governance_approval,
    load_labels,
    load_lines,
)
from l9_ci.governance.thresholds import (
    ThresholdPolicyError,
    format_threshold_policy,
    load_threshold_policy,
)
from l9_ci.governance.rule_modes import RuleModePolicyError, format_rule_mode_policy, load_rule_mode_policy
from l9_ci.bootstrap.new_repo import format_result, init_repo
from l9_ci.governance import banned_imports, terminology_guard
from l9_ci.scanners import deprecated_api, packet_envelope
from l9_ci.pipeline.runner import format_results, results_exit_code, run_pipeline
from l9_ci.agent_payload import AgentPayloadError, render_agent_payload
from l9_ci.review import render_comment, run_review


def _paths(values: list[str]) -> list[Path]:
    return [Path(v) for v in values]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="l9-ci")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("check-transport-packet")
    p.add_argument("paths", nargs="*", default=["."])
    p.add_argument("--exclude", action="append", default=[], help="Path suffix to exclude from scan")
    p.add_argument("--file-mode", choices=["auto", "git_tracked", "working_tree", "filesystem"], default="auto")

    p = sub.add_parser("check-deprecated-api")
    p.add_argument("paths", nargs="*", default=["."])
    p.add_argument("--exclude", action="append", default=[], help="Path suffix to exclude from scan")
    p.add_argument("--file-mode", choices=["auto", "git_tracked", "working_tree", "filesystem"], default="auto")

    p = sub.add_parser("fix-deprecated-api")
    p.add_argument("paths", nargs="*", default=["."])
    p.add_argument("--exclude", action="append", default=[], help="Path suffix to exclude from fix")
    p.add_argument("--zero-on-change", action="store_true")
    p.add_argument("--file-mode", choices=["auto", "git_tracked", "working_tree", "filesystem"], default="auto")

    p = sub.add_parser("terminology-guard")
    p.add_argument("paths", nargs="*", default=["."])
    p.add_argument("--include", action="append", default=[])
    p.add_argument("--exclude", action="append", default=[], help="Path suffix to exclude from scan")
    p.add_argument("--file-mode", choices=["auto", "git_tracked", "working_tree", "filesystem"], default="auto")

    p = sub.add_parser("banned-imports")
    p.add_argument("paths", nargs="*", default=["."])
    p.add_argument("--module", required=True)
    p.add_argument("--path-prefix")
    p.add_argument("--allow", action="append", default=[])
    p.add_argument("--exclude", action="append", default=[], help="Path suffix to exclude from scan")
    p.add_argument("--file-mode", choices=["auto", "git_tracked", "working_tree", "filesystem"], default="auto")

    p = sub.add_parser("gate")
    p.add_argument("--result", action="append", default=[], help="name=status")
    p.add_argument("--required", help="Comma-separated required job names")
    p.add_argument("--input-dir", help="Directory containing *_ci_summary.json files")
    p.add_argument("--emit-agent-payload", help="Write aggregated agent review payload JSON")
    p.add_argument("--changed-file", action="append", default=[], help="Changed file path")
    p.add_argument("--changed-files-file", help="File containing changed file paths, one per line")
    p.add_argument("--pr-label", action="append", default=[], help="Observed PR label")
    p.add_argument("--pr-labels-file", help="JSON file containing PR labels")
    p.add_argument("--labels-unknown", action="store_true", help="Fail closed if governance files changed")

    p = sub.add_parser("validate-thresholds")
    p.add_argument("--policy", default=".github/governance/quality-thresholds.yaml")
    p.add_argument("--bootstrap-mode", action="store_true", help="Use internal bootstrap floor only for init-repo")

    p = sub.add_parser("validate-rule-modes")
    p.add_argument("--policy", default=".github/governance/rule-modes.yaml")

    p = sub.add_parser("validate-governance-approval")
    p.add_argument("--changed-file", action="append", default=[])
    p.add_argument("--changed-files-file")
    p.add_argument("--pr-label", action="append", default=[])
    p.add_argument("--pr-labels-file")
    p.add_argument("--labels-unknown", action="store_true")


    p = sub.add_parser("render-agent-payload")
    p.add_argument("--input-dir", required=True, help="Directory containing *_ci_summary.json files")
    p.add_argument("--output", required=True, help="Output agent_review_payload.json path")
    p.add_argument("--repo-root", default=".")
    p.add_argument("--required-stage", action="append", default=[])
    p.add_argument("--optional-stage", action="append", default=[])

    p = sub.add_parser("run-pipeline")
    p.add_argument("--stage", choices=["classify", "validate", "lint", "test", "security", "transport-contract", "deprecated-api", "thresholds", "gate"])
    p.add_argument("--root", default=".")
    p.add_argument("--ci", choices=["github", "local"], default=None)
    p.add_argument("--matrix", action="append", default=[], help="Matrix value as key=value; may be repeated")
    p.add_argument("--matrix-id", help="Explicit collision-safe matrix identifier")
    p.add_argument("--emit-json", help="Write stage result JSON to an explicit file path")
    p.add_argument("--emit-dir", help="Write stage result JSON into a directory using stage+matrix filename")

    p = sub.add_parser("init-repo")
    p.add_argument("path", nargs="?", default=".")
    p.add_argument("--force", action="store_true", help="Overwrite existing bootstrap files")

    p = sub.add_parser("review")
    p.add_argument("--root", default=".")
    p.add_argument("--changed-file", action="append", default=[], help="Changed file path")
    p.add_argument("--changed-files-file", help="File with changed file paths, one per line")
    p.add_argument("--agent", action="append", default=[], help="Review agent to run (default: audit)")
    p.add_argument("--agent-mode", action="append", default=[], help="agent=mode (shadow|advisory|blocking)")
    p.add_argument("--pr-class", default="unknown_diff")
    p.add_argument("--blocking-policy", help="Path to blocking-policy.yaml (review_blocking_promotions)")
    p.add_argument("--file-mode", choices=["auto", "git_tracked", "working_tree", "filesystem"], default="git_tracked")
    p.add_argument("--trace-id", default="")
    p.add_argument("--emit-json", help="Write the review report JSON")
    p.add_argument("--emit-comment", help="Write the rendered PR comment markdown")
    p.add_argument("--strict", action="store_true", help="Exit non-zero on effective blocking findings")

    args = parser.parse_args(argv)

    if args.command == "check-transport-packet":
        violations = packet_envelope.scan(_paths(args.paths), exclude=args.exclude, file_mode=args.file_mode)
        if violations:
            print(packet_envelope.format_violations(violations), file=sys.stderr)
            return 1
        print("TransportPacket contract check passed.")
        return 0

    if args.command == "check-deprecated-api":
        violations = deprecated_api.check(_paths(args.paths), exclude=args.exclude, file_mode=args.file_mode)
        if violations:
            print(deprecated_api.format_violations(violations), file=sys.stderr)
            return 1
        print("Deprecated API check passed.")
        return 0

    if args.command == "fix-deprecated-api":
        changed = deprecated_api.fix(_paths(args.paths), exclude=args.exclude, file_mode=args.file_mode)
        if changed:
            for path in changed:
                print(f"fixed: {path}")
            return 0 if args.zero_on_change else 1
        print("No deprecated API usage found.")
        return 0

    if args.command == "terminology-guard":
        violations = terminology_guard.scan(_paths(args.paths), include_prefixes=args.include, exclude=args.exclude, file_mode=args.file_mode)
        if violations:
            for v in violations:
                print(f"{v.file}:{v.line}: {v.message} ({v.pattern})", file=sys.stderr)
            return 1
        print("Terminology guard passed.")
        return 0

    if args.command == "banned-imports":
        violations = banned_imports.scan(_paths(args.paths), args.module, args.path_prefix, args.allow, exclude=args.exclude, file_mode=args.file_mode)
        if violations:
            for v in violations:
                print(f"{v.file}:{v.line}: {v.message}", file=sys.stderr)
            return 1
        print("Banned imports check passed.")
        return 0

    if args.command == "gate":
        required = [v.strip() for v in (args.required or "validate,lint,test,security").split(",") if v.strip()]
        if args.input_dir:
            try:
                payload = render_agent_payload(
                    input_dir=Path(args.input_dir),
                    output=Path(args.emit_agent_payload) if args.emit_agent_payload else None,
                    repo_root=Path.cwd(),
                    required_stages=required,
                )
            except AgentPayloadError as exc:
                print(str(exc), file=sys.stderr)
                return 1
            if payload["gate_status"] != "pass":
                print("CI gate failed from summary artifacts", file=sys.stderr)
                if args.emit_agent_payload:
                    print(f"agent payload: {args.emit_agent_payload}")
                return 1
            print("CI gate passed from summary artifacts")
            if args.emit_agent_payload:
                print(f"agent payload: {args.emit_agent_payload}")
            return 0
        changed_files = _collect_values(args.changed_file, args.changed_files_file)
        labels = _collect_labels(args.pr_label, args.pr_labels_file)
        result = evaluate(
            parse_result_pairs(args.result),
            required,
            changed_files=changed_files if changed_files else None,
            pr_labels=labels,
            labels_known=not args.labels_unknown,
        )
        print(format_gate(result))
        return 0 if result.passed else 1

    if args.command == "validate-thresholds":
        try:
            policy = load_threshold_policy(Path(args.policy), bootstrap_mode=args.bootstrap_mode)
        except ThresholdPolicyError as exc:
            print(str(exc), file=sys.stderr)
            return 1
        print(format_threshold_policy(policy))
        return 0

    if args.command == "validate-rule-modes":
        try:
            policy = load_rule_mode_policy(Path(args.policy))
        except RuleModePolicyError as exc:
            print(str(exc), file=sys.stderr)
            return 1
        print(format_rule_mode_policy(policy))
        return 0

    if args.command == "validate-governance-approval":
        changed_files = _collect_values(args.changed_file, args.changed_files_file)
        labels = _collect_labels(args.pr_label, args.pr_labels_file)
        result = evaluate_governance_approval(changed_files, labels, labels_known=not args.labels_unknown)
        print(format_governance_approval(result))
        return 0 if result.passed else 1



    if args.command == "render-agent-payload":
        try:
            render_agent_payload(
                input_dir=Path(args.input_dir),
                output=Path(args.output),
                repo_root=Path(args.repo_root),
                required_stages=args.required_stage,
                optional_stages=args.optional_stage,
            )
        except AgentPayloadError as exc:
            print(str(exc), file=sys.stderr)
            return 1
        print(f"Agent review payload written: {args.output}")
        return 0

    if args.command == "run-pipeline":
        try:
            results = run_pipeline(
                root=Path(args.root),
                stage=args.stage,
                ci=args.ci,
                matrix_values=args.matrix,
                matrix_id=args.matrix_id,
                emit_json=args.emit_json,
                emit_dir=args.emit_dir,
            )
        except ValueError as exc:
            print(str(exc), file=sys.stderr)
            return 1
        print(format_results(results))
        return results_exit_code(results)

    if args.command == "init-repo":
        result = init_repo(Path(args.path), force=args.force)
        print(format_result(result))
        return 0

    if args.command == "review":
        import json as _json

        changed = _collect_values(args.changed_file, args.changed_files_file)
        agents = args.agent or ["audit"]
        modes: dict[str, str] = {}
        for pair in args.agent_mode:
            if "=" in pair:
                key, value = pair.split("=", 1)
                modes[key.strip()] = value.strip()
        promotions: set[str] = set()
        if args.blocking_policy:
            import yaml

            data = yaml.safe_load(Path(args.blocking_policy).read_text(encoding="utf-8")) or {}
            promotions = set(data.get("review_blocking_promotions", []) or [])
        report = run_review(
            Path(args.root),
            changed,
            pr_class=args.pr_class,
            agents=agents,
            agent_modes=modes,  # type: ignore[arg-type]
            promotions=promotions,
            file_mode=args.file_mode,
            trace_id=args.trace_id,
        )
        if args.emit_json:
            out = Path(args.emit_json)
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(_json.dumps(report.to_dict(), indent=2), encoding="utf-8")
        if args.emit_comment:
            out = Path(args.emit_comment)
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(render_comment(report), encoding="utf-8")
        print(
            f"review: {report.blocking_count} blocking, "
            f"{report.advisory_count} advisory, {report.shadow_count} shadow"
        )
        return 1 if (args.strict and report.blocking_count) else 0

    return 2


def _collect_values(values: list[str], values_file: str | None) -> list[str]:
    collected = list(values)
    if values_file:
        collected.extend(load_lines(Path(values_file)))
    return collected


def _collect_labels(values: list[str], labels_file: str | None) -> list[str]:
    collected = list(values)
    if labels_file:
        collected.extend(load_labels(Path(labels_file)))
    return collected


if __name__ == "__main__":
    raise SystemExit(main())
