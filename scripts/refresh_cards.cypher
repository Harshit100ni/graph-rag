// ---------- card limits as parameters (persist across the whole file) ----------
:param LIM_STATES => 10;
:param LIM_BTYPES => 10;
:param LIM_CROPS  => 12;
:param LIM_CERTS  => 10;

// ======================= RyzosphereOrganization =======================
MATCH (o:RyzosphereOrganization)
OPTIONAL MATCH (o)-[:HAS_STATE]->(s:State)
WITH o, collect(DISTINCT coalesce(s.code, s.name)) AS states
OPTIONAL MATCH (o)-[:HAS_BUSINESSTYPE]->(b:BusinessType)
WITH o, states, collect(DISTINCT b.name) AS btypes
OPTIONAL MATCH (o)-[:HANDLES_PRODUCT|:STORES_PRODUCT]->(c:Crop)
WITH o, states, btypes, collect(DISTINCT c.name) AS crops
OPTIONAL MATCH (o)-[:HAS_CERTIFICATION]->(cert:Certification)
WITH o, states, btypes, crops, collect(DISTINCT cert.name) AS certs

WITH o,
  coalesce(o.NodeID, labels(o)[0] + ":" + coalesce(o.name,o.code,o.canonical,toString(id(o)))) AS title,
  apoc.coll.sort([x IN states WHERE x IS NOT NULL]) AS s1,
  apoc.coll.sort([x IN btypes WHERE x IS NOT NULL]) AS b1,
  apoc.coll.sort([x IN crops  WHERE x IS NOT NULL]) AS c1,
  apoc.coll.sort([x IN certs  WHERE x IS NOT NULL]) AS ct1

WITH o, title,
  s1, size(s1) AS ts,
  b1, size(b1) AS tb,
  c1, size(c1) AS tc,
  ct1, size(ct1) AS tt

WITH o, title,
  apoc.text.join(CASE WHEN ts <= $LIM_STATES THEN s1 ELSE s1[0..$LIM_STATES] END, ", ") +
  CASE WHEN ts > $LIM_STATES THEN " (+" + toString(ts - $LIM_STATES) + " more)" ELSE "" END AS statesTxt,
  apoc.text.join(CASE WHEN tb <= $LIM_BTYPES THEN b1 ELSE b1[0..$LIM_BTYPES] END, ", ") +
  CASE WHEN tb > $LIM_BTYPES THEN " (+" + toString(tb - $LIM_BTYPES) + " more)" ELSE "" END AS btypesTxt,
  apoc.text.join(CASE WHEN tc <= $LIM_CROPS  THEN c1 ELSE c1[0..$LIM_CROPS ] END, ", ") +
  CASE WHEN tc > $LIM_CROPS  THEN " (+" + toString(tc - $LIM_CROPS ) + " more)" ELSE "" END AS cropsTxt,
  apoc.text.join(CASE WHEN tt <= $LIM_CERTS  THEN ct1 ELSE ct1[0..$LIM_CERTS ] END, ", ") +
  CASE WHEN tt > $LIM_CERTS  THEN " (+" + toString(tt - $LIM_CERTS ) + " more)" ELSE "" END AS certsTxt

WITH o,
  left(
    'Organization: ' + title +
    CASE WHEN statesTxt <> '' THEN '; States: ' + statesTxt ELSE '' END +
    CASE WHEN btypesTxt <> '' THEN '; Business Types: ' + btypesTxt ELSE '' END +
    CASE WHEN cropsTxt  <> '' THEN '; Crops: ' + cropsTxt  ELSE '' END +
    CASE WHEN certsTxt  <> '' THEN '; Certifications: ' + certsTxt ELSE '' END
  , 600) AS newCard

WITH o, o.card AS oldCard, newCard
SET o.card           = newCard,
    o.card_hash      = apoc.util.md5([newCard]),
    o.card_version   = 2,
    o.card_updatedAt = datetime(),
    o:Embeddable,
    o.needsEmbedding = (oldCard IS NULL OR oldCard <> newCard);

// ======================= Crop =======================
MATCH (c:Crop)
OPTIONAL MATCH (o:RyzosphereOrganization)-[:HANDLES_PRODUCT|:STORES_PRODUCT]->(c)
WITH c, apoc.coll.sort(collect(DISTINCT o.name)) AS orgs

WITH c,
  coalesce(c.NodeID, labels(c)[0] + ":" + coalesce(c.name,c.code,c.canonical,toString(id(c)))) AS title,
  orgs, size(orgs) AS t

WITH c, title,
  apoc.text.join(CASE WHEN t <= 8 THEN orgs ELSE orgs[0..8] END, ", ") +
  CASE WHEN t > 8 THEN " (+" + toString(t - 8) + " more)" ELSE "" END AS orgsTxt

WITH c,
  left('Crop: ' + title + CASE WHEN orgsTxt <> '' THEN '; Example orgs: ' + orgsTxt ELSE '' END, 600) AS newCard

WITH c, c.card AS oldCard, newCard
SET c.card           = newCard,
    c.card_hash      = apoc.util.md5([newCard]),
    c.card_version   = 2,
    c.card_updatedAt = datetime(),
    c:Embeddable,
    c.needsEmbedding = (oldCard IS NULL OR oldCard <> newCard);

// ======================= State =======================
MATCH (s:State)
OPTIONAL MATCH (o:RyzosphereOrganization)-[:HAS_STATE]->(s)
WITH s, apoc.coll.sort(collect(DISTINCT o.name)) AS orgs, count(DISTINCT o) AS cnt

WITH s,
  coalesce(s.NodeID, labels(s)[0] + ":" + coalesce(s.code,s.name,s.canonical,toString(id(s)))) AS title,
  orgs, cnt, size(orgs) AS t

WITH s, title, cnt,
  apoc.text.join(CASE WHEN t <= 10 THEN orgs ELSE orgs[0..10] END, ", ") +
  CASE WHEN t > 10 THEN " (+" + toString(t - 10) + " more)" ELSE "" END AS orgsTxt

WITH s,
  left('State: ' + title + '; Orgs: ' + toString(cnt) + CASE WHEN orgsTxt <> '' THEN ' (e.g., ' + orgsTxt + ')' ELSE '' END, 600) AS newCard

WITH s, s.card AS oldCard, newCard
SET s.card           = newCard,
    s.card_hash      = apoc.util.md5([newCard]),
    s.card_version   = 2,
    s.card_updatedAt = datetime(),
    s:Embeddable,
    s.needsEmbedding = (oldCard IS NULL OR oldCard <> newCard);

// ======================= BusinessType =======================
MATCH (b:BusinessType)
OPTIONAL MATCH (o:RyzosphereOrganization)-[:HAS_BUSINESSTYPE]->(b)
WITH b, apoc.coll.sort(collect(DISTINCT o.name)) AS orgs, count(DISTINCT o) AS cnt

WITH b,
  coalesce(b.NodeID, labels(b)[0] + ":" + coalesce(b.name,b.canonical,toString(id(b)))) AS title,
  orgs, cnt, size(orgs) AS t

WITH b, title, cnt,
  apoc.text.join(CASE WHEN t <= 10 THEN orgs ELSE orgs[0..10] END, ", ") +
  CASE WHEN t > 10 THEN " (+" + toString(t - 10) + " more)" ELSE "" END AS orgsTxt

WITH b,
  left('BusinessType: ' + title + '; Orgs: ' + toString(cnt) + CASE WHEN orgsTxt <> '' THEN ' (e.g., ' + orgsTxt + ')' ELSE '' END, 600) AS newCard

WITH b, b.card AS oldCard, newCard
SET b.card           = newCard,
    b.card_hash      = apoc.util.md5([newCard]),
    b.card_version   = 2,
    b.card_updatedAt = datetime(),
    b:Embeddable,
    b.needsEmbedding = (oldCard IS NULL OR oldCard <> newCard);

// ======================= Certification =======================
MATCH (c:Certification)
OPTIONAL MATCH (o:RyzosphereOrganization)-[:HAS_CERTIFICATION]->(c)
WITH c, apoc.coll.sort(collect(DISTINCT o.name)) AS orgs, count(DISTINCT o) AS cnt

WITH c,
  coalesce(c.NodeID, labels(c)[0] + ":" + coalesce(c.name,c.canonical,toString(id(c)))) AS title,
  orgs, cnt, size(orgs) AS t

WITH c, title, cnt,
  apoc.text.join(CASE WHEN t <= 10 THEN orgs ELSE orgs[0..10] END, ", ") +
  CASE WHEN t > 10 THEN " (+" + toString(t - 10) + " more)" ELSE "" END AS orgsTxt

WITH c,
  left('Certification: ' + title + '; Orgs: ' + toString(cnt) + CASE WHEN orgsTxt <> '' THEN ' (e.g., ' + orgsTxt + ')' ELSE '' END, 600) AS newCard

WITH c, c.card AS oldCard, newCard
SET c.card           = newCard,
    c.card_hash      = apoc.util.md5([newCard]),
    c.card_version   = 2,
    c.card_updatedAt = datetime(),
    c:Embeddable,
    c.needsEmbedding = (oldCard IS NULL OR oldCard <> newCard);

// ======================= Generic fallback (any other labels) =======================
MATCH (n)
WHERE n.card IS NULL
CALL {
  WITH n
  OPTIONAL MATCH (n)-[r]-(m)
  WITH type(r) AS rel, labels(m)[0] AS lbl,
       coalesce(m.name,m.code,m.canonical,m.NodeID) AS val, count(*) AS c
  WITH rel, lbl, apoc.coll.sort(collect(DISTINCT val)) AS vals, sum(c) AS cnt
  WITH rel, lbl, vals, cnt,
       apoc.text.join(CASE WHEN size(vals) <= 5 THEN vals ELSE vals[0..5] END, ", ") AS head,
       CASE WHEN size(vals) > 5 THEN " (+" + toString(size(vals)-5) + " more)" ELSE "" END AS more
  RETURN apoc.text.join(collect(rel + "→" + lbl + ": " + head + more), "; ") AS neigh
}
WITH n, neigh,
  coalesce(n.NodeID, labels(n)[0] + ":" + coalesce(n.name,n.code,n.canonical,toString(id(n)))) AS title
WITH n,
  left(labels(n)[0] + ": " + title + CASE WHEN neigh <> "" THEN "; " + neigh ELSE "" END, 600) AS newCard
SET n.card           = newCard,
    n.card_hash      = apoc.util.md5([newCard]),
    n.card_version   = 2,
    n.card_updatedAt = datetime(),
    n:Embeddable,
    n.needsEmbedding = true;
