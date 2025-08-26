def make_triple_facts(rows):
    lines, cites = ["FACTS"], set()
    for r in rows or []:
        a, rel, b = r.get("a"), r.get("rel"), r.get("b")
        if a and rel and b:
            lines.append(f"- ({a}) {rel} ({b})")
            cites.add(a); cites.add(b)
    if len(lines) == 1:
        lines.append("- (none)")
    return "\n".join(lines), sorted(cites)
