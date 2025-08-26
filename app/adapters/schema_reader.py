from app.adapters.neo4j_client import run_read

def relationship_filter() -> str:
    rows = run_read("CALL db.relationshipTypes() YIELD relationshipType RETURN relationshipType")
    return "|".join(sorted({r["relationshipType"] for r in rows}))

def label_filter() -> str:
    rows = run_read("CALL db.labels() YIELD label RETURN label")
    labs = sorted({r["label"] for r in rows})
    return "+" + "|+".join(labs)
