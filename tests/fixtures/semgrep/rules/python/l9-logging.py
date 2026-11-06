# Regression fixture for l9_ci/rulesets/semgrep/python/l9-logging.yml.
#
# Run with: semgrep --test --config l9_ci/rulesets/semgrep/python \
#               tests/fixtures/semgrep/rules/python
# (tests/rulesets/test_semgrep_rule_fixtures.py does exactly this.)
#
# Lines annotated ruleid are real secret leaks the rules MUST flag; lines
# annotated ok are the false positives that failed Quantum-L9/Cognitive.Engine.Graphs PR
# #409 and must stay quiet. This file is scan INPUT, never imported, and is
# listed in .semgrepignore so the SDK's own self-CI scan does not report it.
# ruff: noqa
# type: ignore
import logging
import os

logger = logging.getLogger(__name__)


def ceg_pr409_false_positives(request, path):
    # Prose that merely names a secret-like concept logs no value.
    # ok: l9.logging.forbidden-secret-field
    logger.debug("Failed to decode JWT claims from token", exc_info=True)
    # Implicit string concatenation is still one literal.
    # ok: l9.logging.forbidden-secret-field
    logger.critical(
        "L9_API_KEY is not set or uses a default value. "
        "Authentication is DISABLED — all requests will be rejected."
    )
    # ok: l9.logging.forbidden-secret-field
    logger.warning("Tenant not in token allowed_tenants; request refused")
    # Non-secret values next to secret-like prose.
    # ok: l9.logging.forbidden-secret-field
    logger.warning(
        "Invalid API key: %s %s from %s",
        request.method,
        path,
        request.client.host if request.client else "unknown",
    )
    # ok: l9.logging.forbidden-secret-field
    logger.info("token refresh failed for %s" % request.method)
    # ok: l9.logging.forbidden-secret-field
    logger.info(_("Invalid token"))
    # ok: l9.logging.forbidden-secret-keyword
    logger.info("refresh token=%s rejected", request.method)
    # ok: l9.logging.f-string-secret
    logger.info(f"Refreshing token for {request.method}")


def must_still_catch(api_key, creds, s, self, token, raw_response):
    # ruleid: l9.logging.forbidden-secret-field
    logger.info("x %s", api_key)
    # ruleid: l9.logging.forbidden-secret-field
    logger.info("x %s", self.token)
    # ruleid: l9.logging.forbidden-secret-field
    logger.info("x %s", creds["password"])
    # `extra` keys become LogRecord attributes that structured formatters
    # emit verbatim, so a value filed under a secret-like key is logged.
    # ruleid: l9.logging.forbidden-secret-field
    logger.error("x", extra={"secret": s})
    # ruleid: l9.logging.forbidden-secret-field
    logger.info("%s", get_token())
    # ruleid: l9.logging.forbidden-secret-field
    logger.info("%s", self.get_token())
    # ruleid: l9.logging.forbidden-secret-field
    logger.info("%s", os.getenv("OPENAI_API_KEY"))
    # ruleid: l9.logging.forbidden-secret-field
    logger.info("%s", os.environ["API_KEY"])
    # ruleid: l9.logging.forbidden-secret-field
    logger.info("x %s" % api_key)
    # ruleid: l9.logging.forbidden-secret-field
    logger.info("x {}".format(token))
    # ruleid: l9.logging.forbidden-secret-field
    logger.info("x " + str(creds["password"]))
    # ruleid: l9.logging.forbidden-secret-field
    logging.warning("upstream said %s", raw_response)
    # ruleid: l9.logging.forbidden-secret-field
    logger.log(logging.INFO, "x %s", llm_response.text)
    # ruleid: l9.logging.forbidden-secret-field
    logger.info("x %s", dict(token=token))
    # ruleid: l9.logging.forbidden-secret-field
    logger.info(
        "multi-line %s",
        api_key,
    )


def keyword_rule(token, value):
    # ruleid: l9.logging.forbidden-secret-keyword
    logger.info("login", token=value)
    # ruleid: l9.logging.forbidden-secret-keyword
    logging.error("login", api_key_masked=value)
    # ruleid: l9.logging.forbidden-secret-keyword
    logger.info(
        "wrapped",
        password=value,
    )
    # ok: l9.logging.forbidden-secret-keyword
    logger.info("x", exc_info=True)


def f_string_rule(self, api_key, cfg, base):
    # ruleid: l9.logging.f-string-secret
    logger.info(f"key={api_key}")
    # ruleid: l9.logging.f-string-secret
    logger.info(f"{self.token}")
    # ruleid: l9.logging.f-string-secret
    logger.info(f"pw {cfg['password']}")
    # ruleid: l9.logging.f-string-secret
    logger.info("x %s", f"{get_token()}")
    # ok: l9.logging.f-string-secret
    logger.info(f"calling {base}")


def not_a_logger_call(token):
    # ok: l9.logging.forbidden-secret-field
    logging.getLogger("token_service")
    # ok: l9.logging.forbidden-secret-field
    print("x %s", token)


def eie_12d8b351_token_usage_counts(
    synthesis, resp, total_tokens, elapsed, tokens_used, usage, response, cost_tracker
):
    # LLM usage figures, not credentials: the sixteen AST-LOGGING-001/002
    # findings that blocked Quantum-L9/Enrichment.Inference.Engine at 12d8b351
    # (enrichment_orchestrator.py, convergence/cost_tracker.py, openai_client.py,
    # anthropic_client.py, result_store.py, simulation_bridge.py,
    # convergence_controller.py). They must stay quiet.
    # ok: l9.logging.forbidden-secret-field, l9.logging.forbidden-secret-keyword
    logger.info(
        "pipeline_completed",
        fields_enriched=len(synthesis["fields"]),
        confidence=resp.confidence,
        tokens=total_tokens,
        elapsed_ms=elapsed,
    )
    # ok: l9.logging.forbidden-secret-field, l9.logging.forbidden-secret-keyword
    logger.debug("cost_tracker.record", tokens=tokens_used)
    # ok: l9.logging.forbidden-secret-field, l9.logging.forbidden-secret-keyword
    logger.info(
        "openai_call_success",
        prompt_tokens=usage.get("prompt_tokens"),
        completion_tokens=usage.get("completion_tokens"),
    )
    # ok: l9.logging.forbidden-secret-field, l9.logging.forbidden-secret-keyword
    logger.info(
        "anthropic_call_success",
        input_tokens=usage.get("input_tokens"),
        output_tokens=usage.get("output_tokens"),
    )
    # ok: l9.logging.forbidden-secret-field, l9.logging.forbidden-secret-keyword
    logger.info("convergence_run_completed", total_tokens=total_tokens)
    # ok: l9.logging.forbidden-secret-field, l9.logging.forbidden-secret-keyword
    logger.info("sonar_entity_enriched", tokens_used=response.tokens_used)
    # ok: l9.logging.forbidden-secret-field, l9.logging.forbidden-secret-keyword
    logger.info("budget_exhausted", total_tokens=cost_tracker.total_tokens)
    # ok: l9.logging.forbidden-secret-field
    logger.info("usage %s/%s", usage["total_tokens"], cost_tracker.max_tokens)
    # ok: l9.logging.forbidden-secret-keyword
    logger.info("x", tokens=12)
    # ok: l9.logging.forbidden-secret-keyword
    logger.info("x", tokens=len(response.choices))
    # ok: l9.logging.f-string-secret
    logger.info(f"used {response.tokens_used} of {cost_tracker.token_budget}")
    # ok: l9.logging.forbidden-secret-field
    logger.info("tokenizer=%s", response.tokenizer)


def credential_tokens_still_caught(
    access_token, refresh_tokens, auth, user, session, cache, generated_tokens
):
    # A token-count exemption must never cover a credential.
    # ruleid: l9.logging.forbidden-secret-field
    logger.info("x %s", access_token)
    # ruleid: l9.logging.forbidden-secret-field
    logger.info("x %s", refresh_tokens)
    # ruleid: l9.logging.forbidden-secret-field
    logger.info("x %s", auth.access_token)
    # ruleid: l9.logging.forbidden-secret-field
    logger.info("x %s", session["refresh_token"])
    # ruleid: l9.logging.forbidden-secret-field, l9.logging.forbidden-secret-keyword
    logger.info("x", access_token=access_token)
    # A credential qualifier voids the count form: the keyword NAME is
    # reported (the value is a count attribute, so AST-LOGGING-001 is quiet).
    # ruleid: l9.logging.forbidden-secret-keyword
    logger.info("x", auth_tokens_used=auth.tokens_used)
    # ruleid: l9.logging.forbidden-secret-field
    logger.info("x %s", auth.refresh_tokens_count)
    # Ambiguous qualifiers are not exempt.
    # ruleid: l9.logging.forbidden-secret-field
    logger.info("x %s", cache.cached_tokens)
    # ruleid: l9.logging.forbidden-secret-field
    logger.info("x %s", generated_tokens)
    # ruleid: l9.logging.forbidden-secret-field
    logger.info("x %s", os.getenv("GITHUB_ACCESS_TOKEN"))
    # A bare `tokens=` keyword whose value is not a proven count is reported.
    # ruleid: l9.logging.forbidden-secret-field, l9.logging.forbidden-secret-keyword
    logger.info("x", tokens=refresh_tokens)
    # ruleid: l9.logging.forbidden-secret-keyword
    logger.info("x", tokens=user.credentials)
    # ruleid: l9.logging.forbidden-secret-field, l9.logging.forbidden-secret-keyword
    logger.info("x", tokens=user.tokens)
    # ruleid: l9.logging.f-string-secret
    logger.info(f"rotated {refresh_tokens}")
    # ruleid: l9.logging.f-string-secret
    logger.info(f"issued {auth.access_token}")
