from __future__ import annotations

UNIVERSAL_GITLEAKS_RULES = [
    "openai-api-key",
    "openai-project-key",
    "perplexity-api-key",
    "generic-api-key",
    "aws-access-key",
    "slack-bot-token",
    "postgres-connection-string",
    "redis-connection-string",
    "neo4j-connection",
    "neo4j-password-assignment",
    "private-key",
    "jwt-token",
    "sendgrid-api-key",
]


def expected_rules() -> list[str]:
    return list(UNIVERSAL_GITLEAKS_RULES)
