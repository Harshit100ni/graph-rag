from .neo import run_read

def get_relationship_filter() -> str:
    rows = run_read("CALL db.relationshipTypes() YIELD relationshipType RETURN relationshipType")
    rels = [r["relationshipType"] for r in rows]
    # No direction markers => both directions; join by '|'
    return "|".join(sorted(set(rels)))

def get_label_filter() -> str:
    rows = run_read("CALL db.labels() YIELD label RETURN label")
    labels = [r["label"] for r in rows]
    # '+Label' means "allow"; combine into a whitelist
    return "+" + "|+".join(sorted(set(labels)))