from typing import List, Tuple


#Not preffered due to hard coding logics
def make_facts(org_rows: list[dict]) -> tuple[str, list[str]]:
    """
    rows look like:
      {
        "org": "RyzosphereOrganization:Acme Grain",
        "states": ["State:WA", ...],
        "btypes": ["BusinessType:Blending", ...],
        "crops":  ["Crop:Beans", ...],
        "certs":  ["Certification:Non-GMO", ...]
      }
    """
    lines: List[str] = []
    cites: set[str] = set()
    for row in org_rows:
        org = row.get("org")
        if not org:
            continue
        cites.add(org)
        for s in row.get("states", []):
            lines.append(f"- ({org}) HAS_STATE ({s})")
            cites.add(s)
        for b in row.get("btypes", []):
            lines.append(f"- ({org}) HAS_BUSINESSTYPE ({b})")
            cites.add(b)
        for c in row.get("crops", []):
            lines.append(f"- ({org}) HANDLES_PRODUCT ({c})")
            cites.add(c)
        for cert in row.get("certs", []):
            lines.append(f"- ({org}) HAS_CERTIFICATION ({cert})")
            cites.add(cert)

    facts = "FACTS\n" + ("\n".join(lines) if lines else "- (none)")
    return facts, sorted(cites)

#prefered

def make_triple_facts(rows: list[dict]) -> tuple[str, list[str]]:
    lines = ["FACTS"]
    cites = set()
    for r in rows or []:
        a, rel, b = r.get("a"), r.get("rel"), r.get("b")
        if not (a and rel and b):
            continue
        lines.append(f"- ({a}) {rel} ({b})")
        cites.add(a); cites.add(b)
    if len(lines) == 1:
        lines.append("- (none)")
    return "\n".join(lines), sorted(cites)