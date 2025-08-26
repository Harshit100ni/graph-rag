from .embeddings import embed_one
from .neo import run_read
from .neo_schema import get_relationship_filter, get_label_filter
from .config import settings

def semantic_knn_generic(question: str, k: int = 8):
    """KNN over whatever index name you configured (settings.vector_index)."""
    qemb = embed_one(question)
    cypher = """
    CALL db.index.vector.queryNodes($index, $k, $qEmbedding)
    YIELD node, score
    RETURN elementId(node) AS id,
           labels(node) AS labels,
           coalesce(node.NodeID, labels(node)[0] + ':' + coalesce(node.code, node.name)) AS nodeId,
           score
    """
    return run_read(cypher, {"index": settings.vector_index, "k": k, "qEmbedding": qemb})

def hybrid_retriever_generic(question: str, k: int = 8, per_seed: int = 20, org_limit: int = 25):
    seeds = semantic_knn_generic(question, k=k)     # <- no index param needed
    if not seeds:
        return []
    seed_ids     = [s["id"] for s in seeds]
    rel_filter   = get_relationship_filter()
    label_filter = get_label_filter()

    cypher = """
    UNWIND $seedIds AS id
    MATCH (seed) WHERE elementId(seed)=id
    CALL apoc.path.expandConfig(seed, {
      minLevel: 1, maxLevel: 1, bfs: true, limit: $perSeed,
      relationshipFilter: $relFilter,
      labelFilter: $labelFilter
    }) YIELD path
    WITH seed, relationships(path) AS rs, nodes(path) AS ns
    UNWIND rs AS r
    WITH seed, r, ns[1] AS nbr
    RETURN DISTINCT
      coalesce(seed.NodeID, labels(seed)[0] + ':' + coalesce(seed.code, seed.name)) AS a,
      type(r) AS rel,
      coalesce(nbr.NodeID, labels(nbr)[0] + ':' + coalesce(nbr.code, nbr.name))     AS b
    LIMIT $orgLimit
    """
    return run_read(cypher, {
        "seedIds": seed_ids,
        "relFilter": rel_filter,
        "labelFilter": label_filter,
        "perSeed": per_seed,
        "orgLimit": org_limit
    })
