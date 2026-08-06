"""Versioned canonical trace schema used by every adapter and view."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Event(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_id: str
    step_index: int = Field(ge=0)
    actor_id: str | None = None
    actor_role: str | None = None
    display_name: str | None = None
    component_type: str | None = None
    event_type: str
    parent_event_ids: list[str] = Field(default_factory=list)
    dependency_event_ids: list[str] = Field(default_factory=list)
    input: dict[str, Any] = Field(default_factory=lambda: {"text": None, "structured": None})
    output: dict[str, Any] = Field(default_factory=lambda: {"text": None, "structured": None})
    tool: dict[str, Any] = Field(default_factory=lambda: {"name": None, "arguments": None, "result": None})
    retrieval: dict[str, Any] = Field(default_factory=lambda: {"query": None, "documents": None})
    memory: dict[str, Any] = Field(default_factory=lambda: {"operation": None, "key": None, "version": None, "source_event_id": None})
    status: str = "ok"
    exception: str | None = None
    logical_time: int | None = None
    source_pointer: str | None = None


class Labels(BaseModel):
    model_config = ConfigDict(extra="forbid")

    is_fault: bool
    fault_type: str | None = None
    origin_component: str | None = None
    origin_actor_id: str | None = None
    origin_event_id: str | None = None
    origin_step_index: int | None = None
    activation_event_id: str | None = None
    first_visible_deviation_event_id: str | None = None
    causal_witness_event_ids: list[str] = Field(default_factory=list)
    propagation_edges: list[tuple[str, str]] = Field(default_factory=list)
    symptom_event_ids: list[str] = Field(default_factory=list)
    terminal_failure_event_id: str | None = None
    label_source: str | None = None


class CanonicalTrace(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = "1.0.0"
    trace_id: str
    source_dataset: str
    source_record_id: str
    source_revision: str
    task_id: str
    workflow_id: str
    framework: str
    topology: str
    modality: str = "text"
    events: list[Event]
    labels: Labels
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_references(self) -> "CanonicalTrace":
        ids = {event.event_id for event in self.events}
        if len(ids) != len(self.events):
            raise ValueError("event_id values must be unique")
        for event in self.events:
            unknown = set(event.parent_event_ids + event.dependency_event_ids) - ids
            if unknown:
                raise ValueError(f"{event.event_id} references unknown events: {sorted(unknown)}")
        origin = self.labels.origin_event_id
        if origin is not None and origin not in ids:
            raise ValueError("origin_event_id must be present in events")
        if self.labels.is_fault and origin is None:
            raise ValueError("fault traces require origin_event_id")
        for name, event_id in (
            ("activation_event_id", self.labels.activation_event_id),
            ("first_visible_deviation_event_id", self.labels.first_visible_deviation_event_id),
        ):
            if event_id is not None and event_id not in ids:
                raise ValueError(f"{name} must be present in events")
        unknown_witnesses = set(self.labels.causal_witness_event_ids) - ids
        if unknown_witnesses:
            raise ValueError(f"causal_witness_event_ids reference unknown events: {sorted(unknown_witnesses)}")
        unknown_edges = {
            endpoint
            for edge in self.labels.propagation_edges
            for endpoint in edge
            if endpoint not in ids
        }
        if unknown_edges:
            raise ValueError(f"propagation_edges reference unknown events: {sorted(unknown_edges)}")
        unknown_symptoms = set(self.labels.symptom_event_ids) - ids
        if unknown_symptoms:
            raise ValueError(f"symptom_event_ids reference unknown events: {sorted(unknown_symptoms)}")
        terminal = self.labels.terminal_failure_event_id
        if terminal is not None and terminal not in ids:
            raise ValueError("terminal_failure_event_id must be present in events")
        return self
