"""Released RQ3 decision policies."""

ROLE = "You diagnose an AI-agent execution using only visible telemetry."
OUTPUT = (
    "Return only the JSON object. Do not provide an explanation, rationale, "
    "candidate list, or additional text. Return valid json matching the supplied "
    "output schema."
)

POLICIES = {
    "p1_minimal": {
        "id": "rq3_minimal_abstention_v1",
        "policy": (
            "Determine whether the visible telemetry uniquely identifies one failure-origin "
            "component and one failure-origin event.\n\nIf it does, return ANSWERABLE with "
            "that component and event.\n\nIf it does not, return INSUFFICIENT_EVIDENCE "
            "with both origin fields set to null."
        ),
    },
    "p2_evidence_gate": {
        "id": "rq3_evidence_gate_v1",
        "policy": (
            "Return ANSWERABLE only when the visible telemetry provides explicit evidence "
            "that satisfies all of the following:\n\n1. It identifies one specific origin "
            "event and one specific origin component.\n2. It connects that event and component "
            "to the observed failure.\n3. It distinguishes that origin from other reasonable "
            "origin candidates.\n\nIf any of these requirements is not satisfied by the visible "
            "telemetry, return INSUFFICIENT_EVIDENCE with both origin fields set to null."
        ),
    },
    "p3_contrastive": {
        "id": "rq3_contrastive_elimination_v1",
        "policy": (
            "Before deciding whether to answer, internally consider whether at least "
            "two different origin hypotheses could still explain the visible telemetry."
            "\n\nReturn ANSWERABLE only if the visible evidence rules out reasonable "
            "alternatives and uniquely supports one origin component and one origin "
            "event.\n\nIf two or more origin hypotheses remain consistent with the "
            "visible evidence, return INSUFFICIENT_EVIDENCE with both origin fields "
            "set to null.\n\nPerform this comparison internally. Output only the "
            "required JSON object."
        ),
    },
}


def apply_policy(base: dict, policy: str) -> dict:
    return {
        "instruction": f"{ROLE}\n\n{policy}\n\n{OUTPUT}",
        "candidate_event_ids": base["candidate_event_ids"],
        "candidate_components": base["candidate_components"],
        "rendered_telemetry": base["rendered_telemetry"],
        "output_schema": base["output_schema"],
    }
