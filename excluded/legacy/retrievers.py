from .neo import run_read
from .embeddings import embed_one
from .config import settings

REL_PRIOR = ['HAS_STATE','HAS_BUSINESSTYPE','HANDLES_PRODUCT','STORES_PRODUCT','HAS_CERTIFICATION']

def _nid(alias: str) -> str:
    # coalesce a human-friendly NodeID when missing
    return f"coalesce({alias}.NodeID, labels({alias})[0] + ':' + coalesce({alias}.code, {alias}.name))"

def semantic_knn(question: str, k: int = 8) -> list[dict]:
    qemb = embed_one(question)
    cypher = f"""
    CALL db.index.vector.queryNodes($index, $k, $qEmbedding)
    YIELD node, score
    RETURN elementId(node) AS id,
           labels(node) AS labels,
           {_nid('node')} AS nodeId,
           score
    """
    return run_read(cypher, {"index": settings.vector_index, "k": k, "qEmbedding": qemb})

def pattern_retriever(state: str | None = None, crop: str | None = None,
                      business_type: str | None = None, cert: str | None = None, limit: int = 50) -> list[dict]:
    cypher = f"""
    MATCH (o:RyzosphereOrganization)
    OPTIONAL MATCH (o)-[:HAS_STATE]->(s:State)
    OPTIONAL MATCH (o)-[:HAS_BUSINESSTYPE]->(b:BusinessType)
    OPTIONAL MATCH (o)-[:HANDLES_PRODUCT|STORES_PRODUCT]->(c:Crop)
    OPTIONAL MATCH (o)-[:HAS_CERTIFICATION]->(ct:Certification)
    WITH o, collect(DISTINCT s) AS ss, collect(DISTINCT b) AS bs, collect(DISTINCT c) AS cs, collect(DISTINCT ct) AS cts
    WHERE ($state IS NULL OR any(x IN ss WHERE toUpper(coalesce(x.code,x.name)) = toUpper($state)))
      AND ($crop  IS NULL OR any(x IN cs WHERE x.name =~ $cropRegex OR coalesce(x.canonical,'') =~ $cropRegex))
      AND ($bt    IS NULL OR any(x IN bs WHERE x.name =~ $btRegex))
      AND ($cert  IS NULL OR any(x IN cts WHERE x.name =~ $certRegex OR coalesce(x.canonical,'') =~ $certRegex))
    WITH o,
         [x IN ss  WHERE x IS NOT NULL | {_nid('x')}] AS states,
         [x IN bs  WHERE x IS NOT NULL | {_nid('x')}] AS btypes,
         [x IN cs  WHERE x IS NOT NULL | {_nid('x')}] AS crops,
         [x IN cts WHERE x IS NOT NULL | {_nid('x')}] AS certs
    RETURN DISTINCT {_nid('o')} AS org, states, btypes, crops, certs
    LIMIT $limit
    """
    params = {
        "state": state,
        "crop": crop,
        "cropRegex": f"(?i).*\\b{crop}\\b.*" if crop else None,
        "bt": business_type,
        "btRegex": f"(?i).*{business_type}.*" if business_type else None,
        "cert": cert,
        "certRegex": f"(?i).*{cert}.*" if cert else None,
        "limit": limit,
    }
    return run_read(cypher, params)


def hybrid_retriever(question: str, k: int = 8, org_limit: int = 25) -> list[dict]:
    seeds = semantic_knn(question, k=k)
    if not seeds:
        return []
    seed_ids = [r["id"] for r in seeds]

    cypher = f"""
    UNWIND $seedIds AS id
    MATCH (seed) WHERE elementId(seed)=id
    OPTIONAL MATCH (seed)-[r1]-(o1:RyzosphereOrganization)
    WHERE type(r1) IN $rels
    WITH seed, collect(DISTINCT o1) AS orgs
    WITH CASE WHEN seed:RyzosphereOrganization THEN orgs + seed ELSE orgs END AS orgs2
    UNWIND orgs2 AS o
    WITH DISTINCT o LIMIT $orgLimit
    OPTIONAL MATCH (o)-[:HAS_STATE]->(s:State)
    WITH o, collect(DISTINCT s) AS ss
    OPTIONAL MATCH (o)-[:HAS_BUSINESSTYPE]->(b:BusinessType)
    WITH o, ss, collect(DISTINCT b) AS bs
    OPTIONAL MATCH (o)-[:HANDLES_PRODUCT|STORES_PRODUCT]->(c:Crop)
    WITH o, ss, bs, collect(DISTINCT c) AS cs
    OPTIONAL MATCH (o)-[:HAS_CERTIFICATION]->(ct:Certification)
    WITH o, ss, bs, cs, collect(DISTINCT ct) AS cts
    RETURN DISTINCT
      {_nid('o')} AS org,
      [x IN ss  WHERE x IS NOT NULL | {_nid('x')}] AS states,
      [x IN bs  WHERE x IS NOT NULL | {_nid('x')}] AS btypes,
      [x IN cs  WHERE x IS NOT NULL | {_nid('x')}] AS crops,
      [x IN cts WHERE x IS NOT NULL | {_nid('x')}] AS certs
    """
    return run_read(cypher, {"seedIds": seed_ids, "rels": REL_PRIOR, "orgLimit": org_limit})
