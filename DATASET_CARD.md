# TelemetrySuffBench Dataset Card

## Summary

TelemetrySuffBench is a controlled benchmark for failure detection, fault classification, origin localization, and evidence-aware abstention in AI-agent telemetry. Every view is rendered deterministically from a versioned canonical trace, which permits paired comparisons without changing the underlying execution.

## Dataset composition

The main release contains 312 traces: 96 clean controls and 216 fault traces. The fault traces form 108 matched two-source groups. They cover three workflow domains, four event-order topologies, nine origin components, and six delayed-binding operators. Each origin component appears in 24 main-set fault traces. The two fault labels are `wrong_reference_binding` (144 traces) and `stale_reference_state` (72 traces).

The seeded holdout contains 216 additional traces: 72 clean controls and 144 fault traces in 72 matched groups. It uses new task instances from the same controlled generator family and seed `20260730`.

## Construction

Each workflow resolves a reference and later updates one target object. A fault is injected when one component selects a stale or alternate binding. Activation, the first visible deviation, the downstream symptom, and the terminal check occur later. For every matched fault group, two traces share the task, delayed-binding mechanism, downstream manifestation, and terminal outcome while differing in the component and event that introduced the fault.

RQ3 searches the 128 seven-factor telemetry masks for paired traces whose complete model-visible payloads are byte-identical after canonical JSON serialization. These collisions provide constructive `INSUFFICIENT_EVIDENCE` cases. Distinct compact and rich views of the same traces provide answerable controls.

## Schema and labels

Canonical traces contain ordered events, component identity, event relations, decision content, tool and state observations, verification evidence, and terminal status. Labels identify whether a fault exists, the closed fault type, the origin component and event, activation and first-visible-deviation events, propagation witnesses, symptom events, and the terminal failure event.

Labels, injection records, and scoring metadata are never included in model-visible requests. Candidate label sets and visible event identifiers are supplied by the corresponding protocol builder.

## Intended use

The dataset supports paired evaluation of which telemetry representations and semantic factors preserve origin evidence, and whether a model abstains when two origins are observationally indistinguishable. It is designed for controlled diagnostic evaluation, not for estimating the prevalence of real production incidents.

## Data characteristics

The traces are synthetic and programmatically controlled. They contain no personal data. The main split uses seed `20260729` for frozen group and bootstrap procedures. The holdout generator uses seed `20260730`.

## Known constraints

The benchmark covers one delayed-reference mechanism family, three task domains, and a closed two-class fault taxonomy. Results should be interpreted as evidence about the evaluated protocols and traces, not as universal performance over all agent systems or telemetry schemas.
