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
