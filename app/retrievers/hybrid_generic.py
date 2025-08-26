from app.adapters.neo4j_client import run_read
from app.adapters.schema_reader import relationship_filter, label_filter
from app.retrievers.semantic import knn

def retrieve(question: str, k: int = 8, per_seed: int = 20, limit: int = 25):
    seeds = knn(question, k=k)
    if not seeds:
        return []
    seed_ids = [s["id"] for s in seeds]
    cypher = """
    UNWIND $seedIds AS id
    MATCH (seed) WHERE elementId(seed)=id
    CALL apoc.path.expandConfig(seed, {
      minLevel: 1, maxLevel: 1, bfs: true, limit: $perSeed,
      relationshipFilter: $relFilter,
      labelFilter: $labFilter
    }) YIELD path
    WITH seed, relationships(path) AS rs, nodes(path) AS ns
    UNWIND rs AS r
    WITH seed, r, ns[1] AS nbr
    RETURN DISTINCT
      coalesce(seed.NodeID, labels(seed)[0] + ':' + coalesce(seed.code, seed.name)) AS a,
      type(r) AS rel,
      coalesce(nbr.NodeID, labels(nbr)[0] + ':' + coalesce(nbr.code, nbr.name))     AS b
    LIMIT $limit
    """
    return run_read(cypher, {
        "seedIds": seed_ids,
        "perSeed": per_seed,
        "relFilter": relationship_filter(),
        "labFilter": label_filter(),
        "limit": limit,
    })
