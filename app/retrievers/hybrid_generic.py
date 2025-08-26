# app/retrievers/hybrid_generic.py
from app.adapters.schema_reader import relationship_filter, label_filter
from app.adapters.neo4j_client import run_read
from app.services.embeddings import embed_one
from app.core.settings import settings

def knn(question: str, k: int = 8):
    vec = embed_one(question)
    return run_read("""
      CALL db.index.vector.queryNodes($index, $k, $vec)
      YIELD node, score
      RETURN elementId(node) AS id,
             labels(node) AS labels,
             coalesce(node.NodeID, labels(node)[0] + ':' + coalesce(node.code, node.name)) AS nodeId,
             score
    """, {"index": settings.vector_index, "k": k, "vec": vec})

def retrieve(question: str, k: int = 8, per_seed: int = 20, limit: int = 50):
    seeds = knn(question, k=k)
    if not seeds: return []
    ids = [s["id"] for s in seeds]
    return run_read("""
      UNWIND $ids AS id
      MATCH (seed) WHERE elementId(seed)=id
      CALL apoc.path.expandConfig(seed, {
        minLevel: 1, maxLevel: 1, bfs: true, limit: $perSeed,
        relationshipFilter: $relFilter, labelFilter: $labFilter
      }) YIELD path
      WITH seed, nodes(path) AS ns, relationships(path) AS rs
      WITH seed, ns[1] AS nbr, head(rs) AS r
      RETURN DISTINCT
        coalesce(seed.NodeID, labels(seed)[0] + ':' + coalesce(seed.code, seed.name)) AS a,
        type(r) AS rel,
        coalesce(nbr.NodeID, labels(nbr)[0] + ':' + coalesce(nbr.code, nbr.name)) AS b
      LIMIT $limit
    """, {
      "ids": ids, "perSeed": per_seed, "limit": limit,
      "relFilter": relationship_filter(), "labFilter": label_filter(),
    })
