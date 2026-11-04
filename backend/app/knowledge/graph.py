"""Reading the knowledge graph back out, shaped for the Cytoscape view.

Two kinds of edge: "relation" edges are facts the LLM extracted ("Maria Okafor -appointed->
Halden & Rowe"); "cooccurrence" edges link entities named in the same passage, weighted by
how many passages they share. A pair with a relation isn't also drawn as co-occurring.
"""
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

_DOCUMENT_ENTITIES = text("""
    SELECT e.id, e.name, e.type, sum(m.count) AS mentions
      FROM entity_mentions m JOIN entities e ON e.id = m.entity_id
     WHERE m.document_id = :document_id
     GROUP BY e.id
     ORDER BY mentions DESC, e.name
     LIMIT :limit
""")

_LIBRARY_ENTITIES = text("""
    SELECT e.id, e.name, e.type, sum(m.count) AS mentions, count(DISTINCT m.document_id) AS doc_count
      FROM entity_mentions m
      JOIN entities e ON e.id = m.entity_id
      JOIN documents d ON d.id = m.document_id AND d.status = 'ready'
     WHERE e.user_id = :user_id
     GROUP BY e.id
     ORDER BY doc_count DESC, mentions DESC, e.name
     LIMIT :limit
""")

_RELATIONS = text("""
    SELECT r.source_id, r.target_id, r.predicate, count(*) AS weight
      FROM relations r
     WHERE r.source_id = ANY(:ids) AND r.target_id = ANY(:ids)
       AND (CAST(:document_id AS integer) IS NULL OR r.document_id = :document_id)
     GROUP BY r.source_id, r.target_id, r.predicate
""")

_COOCCURRENCE = text("""
    SELECT a.entity_id AS source_id, b.entity_id AS target_id, count(*) AS weight
      FROM entity_mentions a
      JOIN entity_mentions b ON b.chunk_id = a.chunk_id AND a.entity_id < b.entity_id
     WHERE a.entity_id = ANY(:ids) AND b.entity_id = ANY(:ids)
       AND (CAST(:document_id AS integer) IS NULL OR a.document_id = :document_id)
     GROUP BY a.entity_id, b.entity_id
     ORDER BY weight DESC
     LIMIT :edge_limit
""")


async def document_entities(session: AsyncSession, document_id: int, limit: int = 200) -> list[dict]:
    rows = await session.execute(_DOCUMENT_ENTITIES, {"document_id": document_id, "limit": limit})
    return [{"id": r.id, "text": r.name, "label": r.type, "mentions": int(r.mentions)} for r in rows]


async def _graph(session: AsyncSession, nodes: list, document_id: int | None, edge_limit: int) -> dict:
    ids = [n.id for n in nodes]
    if not ids:
        return {"nodes": [], "edges": []}
    params = {"ids": ids, "document_id": document_id, "edge_limit": edge_limit}

    edges, related = [], set()
    for r in await session.execute(_RELATIONS, params):
        related.add(frozenset((r.source_id, r.target_id)))
        edges.append({"source": str(r.source_id), "target": str(r.target_id), "label": r.predicate,
                      "kind": "relation", "weight": int(r.weight)})
    for r in await session.execute(_COOCCURRENCE, params):
        if frozenset((r.source_id, r.target_id)) not in related:
            edges.append({"source": str(r.source_id), "target": str(r.target_id), "label": "appears with",
                          "kind": "cooccurrence", "weight": int(r.weight)})

    degree: dict[str, int] = {}
    for e in edges:
        for end in (e["source"], e["target"]):
            degree[end] = degree.get(end, 0) + 1
    return {
        "nodes": [
            {"id": str(n.id), "label": n.name, "type": n.type, "weight": int(n.mentions),
             "degree": degree.get(str(n.id), 0), **({"doc_count": int(n.doc_count)} if hasattr(n, "doc_count") else {})}
            for n in nodes
        ],
        "edges": edges,
    }


async def document_graph(session: AsyncSession, document_id: int, max_nodes: int = 50) -> dict:
    nodes = list(await session.execute(_DOCUMENT_ENTITIES, {"document_id": document_id, "limit": max_nodes}))
    return await _graph(session, nodes, document_id, edge_limit=300)


async def library_graph(session: AsyncSession, user_id: int, max_nodes: int = 80) -> dict:
    nodes = list(await session.execute(_LIBRARY_ENTITIES, {"user_id": user_id, "limit": max_nodes}))
    return await _graph(session, nodes, None, edge_limit=400)
