"""
agent_validator.py
====================
A consistency checker for founder agents, structured after the validator in
Social-Simulations-for-Survey-based-Research (Pia Schnabel).

DESIGN PRINCIPLES (carried over from that reference implementation)
---------------------------------------------------------------------
1. Flag CONTRADICTIONS or UNCONFIGURED DEFAULTS, not unusual-but-plausible
   combinations. Real founders can be, say, both highly Missionary and
   highly Darwinian at once (Ossenbrink et al. found exactly this
   correlation) -- that is a real pattern and must pass. The validator only
   fires on things that indicate a genuine setup mistake: an empty name,
   an implausible age, or a whole settings section left untouched at its
   default when it should have been deliberately set.

2. Severity levels:
     "error"   -- the agent cannot be saved in this state (e.g. no name).
     "warning" -- saveable, but worth a second look before you run an
                  experiment on it (e.g. all four cognitive dials still at
                  the default 5, which likely means they were never
                  actually considered).

3. Every check reads fields defensively (.get) and no-ops on anything
   missing, so the validator is safe on partial/new agents.

USAGE
-----
    from agent_validator import validate_agent

    result = validate_agent(payload)
    if result["errors"]:
        # block the save, show result["errors"] to the user
    if result["warnings"]:
        # save anyway, but surface result["warnings"] as a soft nudge
"""


def _as_int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def check_identity(payload):
    """Errors: things that make the agent unusable. Kept minimal on purpose --
    this is the only hard gate."""
    issues = []
    if not (payload.get("name") or "").strip():
        issues.append({"severity": "error", "field": "name",
                        "message": "Every agent needs a name."})
    return issues


def check_demographics(payload):
    """Soft check: an age can be left blank (source stays 'assigned'/unknown),
    but if one is given it should be a plausible founder age. This is a
    contradiction check, not a taste check -- 14 or 140 are implausible;
    22 or 78 are unusual but real."""
    issues = []
    age = _as_int(payload.get("age"))
    if payload.get("age") not in (None, "") and age is None:
        issues.append({"severity": "warning", "field": "age",
                        "message": "Age isn't a number -- it will be stored as text and won't factor into reasoning as a number."})
    elif age is not None and not (16 <= age <= 95):
        issues.append({"severity": "warning", "field": "age",
                        "message": f"Age {age} is outside a plausible founder range (16-95) -- double check this is intentional."})
    return issues


def check_alignment_strategy_coherence(payload):
    """Soft check: an Engineer with no stated technical domain is a
    plausible-but-worth-flagging gap, since the whole point of the Engineer
    archetype is expertise in a specific technical domain."""
    issues = []
    if payload.get("alignment_strategy") == "engineer" and not (payload.get("expertise") or "").strip():
        issues.append({"severity": "warning", "field": "expertise",
                        "message": "Engineer strategy usually pairs with a stated domain expertise -- this agent has none set."})
    return issues


def check_founder_identity_blend(payload):
    """Soft check: a flat identity blend (all three near the default 5) most
    likely means it was never deliberately considered, not that the founder
    genuinely has no leaning at all. This does NOT flag high-on-multiple-axes
    agents (e.g. Missionary 8 + Darwinian 8) -- that combination is real and
    should pass untouched, per Ossenbrink et al.'s finding that these two
    identities positively correlate in practice.

    Skipped entirely for Tier 2 (interview) agents -- for those, the trait
    scales are optional secondary scaffolding by design, so leaving them at
    default is not an oversight the way it would be for a Tier 1 agent."""
    if payload.get("tier") == "interview":
        return []
    issues = []
    m = _as_int(payload.get("missionary"))
    dar = _as_int(payload.get("darwinian"))
    c = _as_int(payload.get("communitarian"))
    if None not in (m, dar, c) and all(4 <= v <= 6 for v in (m, dar, c)):
        issues.append({"severity": "warning", "field": "founder_identity",
                        "message": "All three founder-identity scores are near the default (5) -- consider deliberately raising at least one."})
    return issues


def check_cognitive_dials(payload):
    """Soft check: same logic as above, applied to the four assigned dials.
    Also skipped for Tier 2 agents, for the same reason."""
    if payload.get("tier") == "interview":
        return []
    issues = []
    keys = ["risk", "bias", "dominance", "optimism"]
    values = [_as_int(payload.get(k)) for k in keys]
    if None not in values and all(v == 5 for v in values):
        issues.append({"severity": "warning", "field": "assigned",
                        "message": "All four cognitive dials are left at the default (5) -- these are meant to be experimental variables you set deliberately."})
    return issues


def check_interview_material(payload):
    """Tier 2 (interview) agents are meaningless without real interview
    content -- this is the equivalent hard requirement to "needs a name"
    for that construction mode."""
    issues = []
    if payload.get("tier") == "interview" and not (payload.get("background") or "").strip():
        issues.append({"severity": "error", "field": "background",
                        "message": "Tier 2 (interview) agents need real interview material in the Background field -- that's what grounds this agent."})
    return issues


def validate_agent(payload):
    """Runs all checks and returns {"errors": [...], "warnings": [...]}.
    `payload` is the same flat dict the Flask routes already build from the
    agent form (see app.py's _agent_payload_to_kwargs input, pre-transform)."""
    checks = [
        check_identity,
        check_demographics,
        check_alignment_strategy_coherence,
        check_founder_identity_blend,
        check_cognitive_dials,
        check_interview_material,
    ]
    all_issues = []
    for check in checks:
        all_issues.extend(check(payload))

    return {
        "errors": [i["message"] for i in all_issues if i["severity"] == "error"],
        "warnings": [i["message"] for i in all_issues if i["severity"] == "warning"],
    }
