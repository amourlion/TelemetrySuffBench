"""Frozen RQ3 construction, scoring, and group-cluster bootstrap.

The only observational-equivalence predicate used here is equality of the
canonicalized *complete model payload*.  Telemetry-body similarity is never
used as a substitute.
"""
from __future__ import annotations

from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import random
from typing import Any, Iterable

from telemetry_suff.rq2.masks import all_masks, mask_from_bits
from telemetry_suff.rq2.offline_analysis import load_traces
from telemetry_suff.rq2.renderer import render_trace

PROTOCOL = "rq3_direct_abstention_v1"
CONDITIONS = ("compact_answerable", "rich_answerable", "sparse_ambiguous", "rich_ambiguous")
ANSWERABLE = {"compact_answerable", "rich_answerable"}

def canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))

def sha(value: Any) -> str:
    return hashlib.sha256(canonical(value).encode()).hexdigest()

def write_jsonl(path: Path, rows: Iterable[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(canonical(x) + "\n" for x in rows), encoding="utf-8")

def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]

def visible_payload(trace: dict, mask_bits: str, components: list[str]) -> dict:
    """Return the sole trace-dependent user payload seen by the model."""
    rendered = render_trace(trace, mask_from_bits(mask_bits))
    if rendered.unknown_fields:
        raise ValueError(f"renderer unknown fields: {rendered.unknown_fields}")
    return {
        "instruction": (
            "Diagnose an AI-agent execution using only the visible telemetry. "
            "Return ANSWERABLE only when one origin component and one visible "
            "origin event are uniquely supported. If two or more origins remain "
            "consistent, or evidence only identifies activation, symptom, or terminal "
            "failure, return INSUFFICIENT_EVIDENCE. Do not infer hidden state. "
            "Return valid json matching the supplied output schema."
        ),
        "candidate_event_ids": list(rendered.candidate_event_ids),
        "candidate_components": components,
        "rendered_telemetry": json.loads(rendered.content),
        "output_schema": {
            "answerability": "ANSWERABLE|INSUFFICIENT_EVIDENCE",
            "origin_component": "visible component|null",
            "origin_event_id": "visible event ID|null",
        },
    }

def payload_hash(payload: dict) -> str:
    return sha(payload)

def nonempty_count(payload: dict) -> int:
    def walk(x: Any) -> int:
        if isinstance(x, dict): return sum(walk(v) for v in x.values())
        if isinstance(x, list): return sum(walk(v) for v in x)
        return int(x not in (None, "", [], {}))
    return walk(payload["rendered_telemetry"])

def _stage(labels: dict) -> dict:
    return {
        "origin": labels["origin_event_id"], "activation": labels["activation_event_id"],
        "first_visible": labels["first_visible_deviation_event_id"],
        "symptom": (labels.get("symptom_event_ids") or [None])[0],
        "terminal": labels["terminal_failure_event_id"],
    }

def build_dataset(root: Path = Path(".")) -> dict:
    traces = [x for x in load_traces(root / "data/canonical/agenttelemetry_component_extension_v1_r3") if x["labels"]["is_fault"]]
    by_group: dict[str, list[dict]] = defaultdict(list)
    for trace in traces: by_group[trace["metadata"]["matched_group_id"]].append(trace)
    components = sorted({t["labels"]["origin_component"] for t in traces})
    masks = all_masks()
    eligible, audit = [], []
    for group_id, pair in sorted(by_group.items()):
        reason = None
        if len(pair) != 2: reason = "group_size_not_two"
        elif pair[0]["labels"]["origin_event_id"] == pair[1]["labels"]["origin_event_id"]: reason = "origins_not_distinct"
        elif pair[0]["metadata"].get("terminal_symptom") != pair[1]["metadata"].get("terminal_symptom"): reason = "terminal_symptom_mismatch"
        if reason:
            audit.append({"matched_group_id": group_id, "eligible": False, "reason": reason}); continue
        payloads = {m.mask_id: [visible_payload(t, m.mask_id[5:], components) for t in pair] for m in masks}
        candidates = [m for m in masks if canonical(payloads[m.mask_id][0]) == canonical(payloads[m.mask_id][1])]
        compact, rich = "1110010", "1111011"
        compact_pair = [visible_payload(t, compact, components) for t in pair]
        rich_pair = [visible_payload(t, rich, components) for t in pair]
        if canonical(compact_pair[0]) == canonical(compact_pair[1]): reason = "compact_answerable_payload_equal"
        elif canonical(rich_pair[0]) == canonical(rich_pair[1]): reason = "rich_answerable_payload_equal"
        elif not candidates: reason = "no_exact_ambiguous_mask"
        else:
            rank_low = lambda m: (m.factor_count, nonempty_count(payloads[m.mask_id][0]), len(canonical(payloads[m.mask_id][0])), m.mask_id)
            rank_high = lambda m: (-m.factor_count, -nonempty_count(payloads[m.mask_id][0]), -len(canonical(payloads[m.mask_id][0])), m.mask_id)
            sparse, ambiguous_rich = min(candidates, key=rank_low), min(candidates, key=rank_high)
            if sparse.mask_id == ambiguous_rich.mask_id: reason = "ambiguous_masks_not_distinct"
            elif ambiguous_rich.factor_count <= sparse.factor_count: reason = "rich_not_strictly_richer"
            else:
                eligible.append({"matched_group_id": group_id, "trace_ids": [t["trace_id"] for t in pair],
                    "sparse_mask_id": sparse.mask_id, "rich_mask_id": ambiguous_rich.mask_id,
                    "sparse_factor_count": sparse.factor_count, "rich_factor_count": ambiguous_rich.factor_count})
        audit.append({"matched_group_id": group_id, "eligible": reason is None, "reason": reason,
                      "candidate_ambiguous_masks": [m.mask_id for m in candidates]})
    out = root / "data/rq3/manifests"; out.mkdir(parents=True, exist_ok=True)
    (root / "outputs/derived").mkdir(parents=True, exist_ok=True)
    (out / "rq3_eligible_groups_v1.json").write_text(json.dumps(eligible, indent=2) + "\n")
    (root / "outputs/derived/rq3_group_eligibility_audit.json").write_text(json.dumps(audit, indent=2) + "\n")
    import csv
    with (root / "outputs/derived/rq3_group_eligibility.csv").open("w", newline="") as f:
        w=csv.DictWriter(f, fieldnames=["matched_group_id","eligible","reason","candidate_ambiguous_masks"]); w.writeheader(); w.writerows(audit)
    return {"eligible": eligible, "audit": audit, "traces": {t["trace_id"]: t for t in traces}, "components": components}

def split_groups(eligible: list[dict], seed: int = 20260729) -> dict[str, list[str]]:
    ids = sorted(x["matched_group_id"] for x in eligible); random.Random(seed).shuffle(ids)
    n = len(ids) // 3
    return {"discovery": sorted(ids[:n]), "confirmation": sorted(ids[n:])}

def build_queues(root: Path = Path("."), model_label: str = "MODEL-ID-TO-BE-SUPPLIED") -> dict:
    built=build_dataset(root); eligible=built["eligible"]; traces=built["traces"]; components=built["components"]
    split=split_groups(eligible); lookup={x["matched_group_id"]:x for x in eligible}
    (root / "data/splits").mkdir(parents=True, exist_ok=True)
    for name, ids in split.items(): (root / f"data/splits/rq3_{name}_groups_v1.txt").write_text("\n".join(ids)+"\n")
    (root / "data/rq3/manifests/rq3_group_split_manifest_v1.json").write_text(json.dumps({"seed":20260729,**split}, indent=2)+"\n")
    counts={}
    for name, ids in split.items():
        logical=[]; requests={}
        for gid in ids:
            group=lookup[gid]
            masks={"compact_answerable":"1110010", "rich_answerable":"1111011", "sparse_ambiguous":group["sparse_mask_id"][5:], "rich_ambiguous":group["rich_mask_id"][5:]}
            for index, trace_id in enumerate(group["trace_ids"]):
                trace=traces[trace_id]; member="ab"[index]
                for condition, bits in masks.items():
                    payload=visible_payload(trace,bits,components); h=payload_hash(payload)
                    jid=sha({"v":1,"split":name,"group":gid,"trace":trace_id,"condition":condition})
                    # Deduplicate only the two identical ambiguous members of
                    # one matched group. Cross-group calls remain independent
                    # as specified by the six-requests-per-group protocol.
                    request_id=sha({"v":1,"split":name,"group":gid,"payload_hash":h})
                    gold={"answerability":"ANSWERABLE","origin_component":trace["labels"]["origin_component"],"origin_event_id":trace["labels"]["origin_event_id"]} if condition in ANSWERABLE else {"answerability":"INSUFFICIENT_EVIDENCE","origin_component":None,"origin_event_id":None}
                    logical.append({"logical_job_id":jid,"request_id":request_id,"split":name,"matched_group_id":gid,"trace_id":trace_id,"pair_member":member,"condition":condition,"mask_id":f"mask_{bits}","observable_payload_hash":h,"gold":gold,"causal_stage_metadata":_stage(trace["labels"]),"candidate_event_ids":payload["candidate_event_ids"],"candidate_components":components})
                    if request_id not in requests: requests[request_id]={"request_id":request_id,"protocol_version":PROTOCOL,"model":model_label,"observable_payload_hash":h,"logical_job_ids":[],"model_visible_payload":payload}
                    requests[request_id]["logical_job_ids"].append(jid)
        write_jsonl(root / f"data/rq3/manifests/rq3_{name}_logical_jobs.jsonl", logical)
        write_jsonl(root / f"outputs/requests/rq3_{name}_p0.jsonl", list(requests.values()))
        counts[name]={"logical_rows":len(logical),"unique_requests":len(requests)}
    return {"split":split,"counts":counts,"eligible_groups":len(eligible)}

def parse_prediction(value: Any, job: dict) -> dict:
    if not isinstance(value,dict): return {"valid":False,"answerability":None,"origin_component":None,"origin_event_id":None}
    a,c,e=value.get("answerability"),value.get("origin_component"),value.get("origin_event_id")
    valid=(a=="INSUFFICIENT_EVIDENCE" and c is None and e is None) or (a=="ANSWERABLE" and c in job["candidate_components"] and e in job["candidate_event_ids"])
    return {"valid":valid,"answerability":a,"origin_component":c,"origin_event_id":e}

def outcome(job: dict, pred: dict) -> str:
    if not pred["valid"]: return "invalid"
    if job["gold"]["answerability"]=="INSUFFICIENT_EVIDENCE": return "correct_abstain" if pred["answerability"]=="INSUFFICIENT_EVIDENCE" else "false_answer"
    if pred["answerability"]=="INSUFFICIENT_EVIDENCE": return "unnecessary_abstain"
    if pred["origin_component"]==job["gold"]["origin_component"] and pred["origin_event_id"]==job["gold"]["origin_event_id"]: return "correct_origin"
    return "wrong_answer"

def metrics(rows: list[dict]) -> dict:
    n=len(rows); by={}
    for cond in CONDITIONS:
        sample=[r for r in rows if r["condition"]==cond]; denom=len(sample); outs=Counter(r["outcome"] for r in sample)
        ans=cond in ANSWERABLE
        by[cond]={"n":denom,"safe_accuracy":(outs["correct_origin"]+outs["correct_abstain"])/denom if denom else 0,"far":outs["false_answer"]/denom if not ans and denom else None,"uar":outs["unnecessary_abstain"]/denom if ans and denom else None,"coverage":sum(r["prediction"]["valid"] and r["prediction"]["answerability"]=="ANSWERABLE" for r in sample)/denom if denom else 0,"joint_accuracy":outs["correct_origin"]/denom if ans and denom else None,"invalid_rate":outs["invalid"]/denom if denom else 0,"outcomes":dict(outs)}
    amb=[r for r in rows if r["condition"] not in ANSWERABLE]; ans=[r for r in rows if r["condition"] in ANSWERABLE]
    return {"n":n,"safe_accuracy":sum(r["outcome"] in {"correct_origin","correct_abstain"} for r in rows)/n if n else 0,"by_condition":by,"far_all":sum(r["outcome"]=="false_answer" for r in amb)/len(amb) if amb else 0,"uar_all":sum(r["outcome"]=="unnecessary_abstain" for r in ans)/len(ans) if ans else 0,"invalid_rate":sum(r["outcome"]=="invalid" for r in rows)/n if n else 0,"richness_bias":by["rich_ambiguous"]["far"]-by["sparse_ambiguous"]["far"],"answerable_richness":by["compact_answerable"]["uar"]-by["rich_answerable"]["uar"]}

def bootstrap(rows: list[dict], repetitions: int=10000, seed: int=20260729) -> dict:
    groups=sorted({r["matched_group_id"] for r in rows}); indexed={g:[r for r in rows if r["matched_group_id"]==g] for g in groups}; rng=random.Random(seed); values=defaultdict(list)
    keys=("safe_accuracy","far_all","uar_all","invalid_rate","richness_bias","answerable_richness",
          "far_sparse","far_rich","uar_compact","uar_rich","joint_compact","joint_rich",
          "compact_restoration","rich_restoration")
    for _ in range(repetitions):
        sample=[x for g in (rng.choice(groups) for _ in groups) for x in indexed[g]]; m=metrics(sample)
        enriched=_bootstrap_values(sample, m)
        for key in keys: values[key].append(enriched[key])
    base=_bootstrap_values(rows, metrics(rows)); return {key:{"estimate":base[key],"ci95":[sorted(v)[int(.025*repetitions)],sorted(v)[int(.975*repetitions)-1]]} for key,v in values.items()}

def _bootstrap_values(rows: list[dict], m: dict | None=None) -> dict:
    m=m or metrics(rows); b=m["by_condition"]
    restored=restoration(rows)
    return {"safe_accuracy":m["safe_accuracy"],"far_all":m["far_all"],"uar_all":m["uar_all"],"invalid_rate":m["invalid_rate"],"richness_bias":m["richness_bias"],"answerable_richness":m["answerable_richness"],"far_sparse":b["sparse_ambiguous"]["far"],"far_rich":b["rich_ambiguous"]["far"],"uar_compact":b["compact_answerable"]["uar"],"uar_rich":b["rich_answerable"]["uar"],"joint_compact":b["compact_answerable"]["joint_accuracy"],"joint_rich":b["rich_answerable"]["joint_accuracy"],"compact_restoration":restored["compact"]["safe_difference"],"rich_restoration":restored["rich"]["safe_difference"]}

def _state(row: dict) -> str:
    return row["outcome"]

def restoration(rows: list[dict]) -> dict:
    by={(r["trace_id"],r["condition"]):r for r in rows}; output={}
    for name, ambiguous, answerable in (("compact","sparse_ambiguous","compact_answerable"),("rich","rich_ambiguous","rich_answerable")):
        table=Counter(); diffs=[]
        for trace_id in sorted({r["trace_id"] for r in rows}):
            a,b=by[(trace_id,ambiguous)],by[(trace_id,answerable)]
            table[f"{_state(a)}__to__{_state(b)}"]+=1
            diffs.append(int(b["outcome"]=="correct_origin")-int(a["outcome"]=="correct_abstain"))
        output[name]={"transitions":dict(sorted(table.items())),"safe_difference":sum(diffs)/len(diffs)}
    return output

def stage_landings(rows: list[dict]) -> dict:
    output={}
    for condition in CONDITIONS:
        counts=Counter()
        for row in (x for x in rows if x["condition"]==condition):
            pred=row["prediction"]
            if not pred["valid"]: stage="invalid"
            elif pred["answerability"]=="INSUFFICIENT_EVIDENCE": stage="abstain"
            else:
                stage=next((name for name,event in row["causal_stage_metadata"].items() if event==pred["origin_event_id"]),"other")
            counts[stage]+=1
        output[condition]=dict(sorted(counts.items()))
    return output
