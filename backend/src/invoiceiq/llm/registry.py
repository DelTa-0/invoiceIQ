"""LLM provider registry — routing by org data-residency policy.

Default: EU-only (Mistral). US providers are per-tenant opt-in. Sovereign
orgs use local models. See docs/02 D7 and docs/13 §5.
"""

ROUTING = {
    "eu_only": {
        "extract": "mistral:medium",
        "classify": "mistral:small",
        "vlm": "mistral:pixtral",
    },
    "us_opt_in": {
        "extract": "openai:gpt-4o-mini|anthropic:claude-haiku",
        "vlm": "gemini:2.5-flash",
    },
    "sovereign": {
        "extract": "local:qwen2.5-7b",
        "vlm": "local:qwen2.5-vl-3b",
    },
}

VALID_POLICIES = frozenset(ROUTING)


def resolve_provider(policy: str, task: str, *, default: str = "eu_only") -> str:
    """Return the configured model route for a tenant policy + pipeline task."""
    if policy not in ROUTING:
        policy = default
    return ROUTING[policy].get(task, ROUTING[default].get(task, "mistral:small"))


def provider_cost_estimate(route: str, tokens: int = 1000) -> float:
    """Rough €/1k-token estimate for cost telemetry (docs/12 §4)."""
    base, _, model = route.partition(":")
    table = {
        ("mistral", "small"): 0.0002,
        ("mistral", "medium"): 0.002,
        ("mistral", "pixtral"): 0.004,
        ("openai", "gpt-4o-mini"): 0.00015,
        ("anthropic", "claude-haiku"): 0.00025,
        ("gemini", "2.5-flash"): 0.0001,
    }
    return tokens * table.get((base, model), 0.001)
