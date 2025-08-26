from neo4j import GraphDatabase
from app.core.settings import settings

_driver = GraphDatabase.driver(settings.neo4j_uri, auth=(settings.neo4j_user, settings.neo4j_pass))

def run_read(cypher: str, params: dict | None = None):
    with _driver.session() as s:
        return list(s.run(cypher, **(params or {})))

def close_driver():
    _driver.close()
