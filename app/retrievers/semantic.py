from app.adapters.neo4j_client import run_read
from app.core.settings import settings
from app.services.embeddings import embed_one

def knn(question: str, k: int = 8):
    qemb = embed_one(question)
    cypher = """
    CALL db.index.vector.queryNodes($index, $k, $v)
    YIELD node, score
    RETURN elementId(node) AS id,
           labels(node) AS labels,
           coalesce(node.NodeID, labels(node)[0] + ':' + coalesce(node.code, node.name)) AS nodeId,
           score
    """
    return run_read(cypher, {"index": settings.vector_index, "k": k, "v": qemb})
