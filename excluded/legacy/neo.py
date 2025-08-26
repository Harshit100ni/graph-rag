from neo4j import GraphDatabase
from .config import settings

# One shared driver for the process
driver = GraphDatabase.driver(settings.neo4j_uri, auth=(settings.neo4j_user, settings.neo4j_pass))

def run_read(cypher: str, params: dict | None = None):
    with driver.session() as sess:
        return list(sess.run(cypher, **(params or {})))
