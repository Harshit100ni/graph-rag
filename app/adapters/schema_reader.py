# app/adapters/schema_reader.py
from functools import lru_cache
from app.adapters.neo4j_client import run_read

@lru_cache(maxsize=1)
def schema_snapshot(max_nodes: int = 200):
    labels = [r["label"] for r in run_read("CALL db.labels() YIELD label RETURN label")]
    rels = [r["relationshipType"] for r in run_read("CALL db.relationshipTypes() YIELD relationshipType RETURN relationshipType")]

    label_props = {}
    for lab in labels:
        rows = run_read(
            f"MATCH (n:`{lab}`) WITH n LIMIT $max "
            f"UNWIND keys(n) AS k RETURN DISTINCT k AS prop ORDER BY prop",
            {"max": max_nodes},
        )
        props = [r["prop"] for r in rows]

        # choose a generic display property for citations
        pref = ["NodeID","nodeId","id","code","name","title","canonical"]
        display_prop = next((p for p in pref if p in props), (props[0] if props else None))

        # sample example values (stringifiable)
        samples = []
        if display_prop:
            vals = run_read(
                f"MATCH (n:`{lab}`) WHERE n.`{display_prop}` IS NOT NULL "
                f"RETURN DISTINCT toString(n.`{display_prop}`) AS v LIMIT 18"
            )
            samples = [r["v"] for r in vals]

        label_props[lab] = {"properties": props, "display_prop": display_prop, "samples": samples}

    return {"labels": labels, "relationships": rels, "label_props": label_props}

def relationship_filter() -> str:
    rels = [r["relationshipType"] for r in run_read("CALL db.relationshipTypes() YIELD relationshipType RETURN relationshipType")]
    return "|".join(sorted(set(rels)))

def label_filter() -> str:
    labs = [r["label"] for r in run_read("CALL db.labels() YIELD label RETURN label")]
    return "+" + "|+".join(sorted(set(labs)))

def schema_text_for_llm(snapshot: dict, max_labels: int = 12) -> str:
    labels = snapshot["labels"][:max_labels]
    rels = snapshot["relationships"]
    parts = [ "Labels: " + ", ".join(labels), "Relationships: " + ", ".join(rels) ]
    for lab in labels:
        meta = snapshot["label_props"].get(lab, {})
        props = ", ".join(meta.get("properties", [])[:16]) or "(none)"
        samps = ", ".join(meta.get("samples", [])[:10]) or "(no examples)"
        parts += [f"{lab} props: {props}", f"{lab} examples: {samps}"]
    return "\n".join(parts)
