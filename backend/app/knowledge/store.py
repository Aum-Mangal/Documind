"""Writing a document's entities, mentions and relations to the database."""
from sqlalchemy import delete, exists, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Entity as EntityRow
from app.db.models import EntityMention, Relation
from app.knowledge.entities import Entity
from app.knowledge.relations import Relation as ExtractedRelation


def apply_type_corrections(entities: dict[str, Entity], types: dict[str, str]) -> None:
    """Applies the LLM's corrected types; NONE removes a name that isn't a real entity."""
    for key, kind in types.items():
        if key not in entities:
            continue
        if kind == "NONE":
            del entities[key]
        else:
            entities[key].type = kind
            entities[key].type_confirmed = True


async def save_graph(
    session: AsyncSession,
    user_id: int,
    document_id: int,
    chunk_ids: list[int],
    entities: dict[str, Entity],
    relations: list[ExtractedRelation],
) -> None:
    """Called inside the transaction that replaces the document's chunks."""
    if entities:
        entities, relations = await _join_library_aliases(session, user_id, entities, relations)
        ids: dict[str, int] = {}
        # Another document may already have this entity: keep its name, and overwrite its type
        # only with one the LLM confirmed (spaCy's guess shouldn't replace a confirmed type)
        for confirmed in (True, False):
            group = [e for e in entities.values() if e.type_confirmed is confirmed]
            if not group:
                continue
            stmt = insert(EntityRow).values(
                [{"user_id": user_id, "canonical": e.key, "name": e.name[:200], "type": e.type} for e in group]
            )
            update_type = stmt.excluded.type if confirmed else EntityRow.type
            stmt = stmt.on_conflict_do_update(index_elements=["user_id", "canonical"], set_={"type": update_type})
            result = await session.execute(stmt.returning(EntityRow.id, EntityRow.canonical))
            ids.update({canonical: entity_id for entity_id, canonical in result.all()})

        session.add_all(
            EntityMention(entity_id=ids[e.key], chunk_id=chunk_ids[index], document_id=document_id, count=count)
            for e in entities.values()
            for index, count in e.mentions.items()
            if index < len(chunk_ids)
        )
        await session.flush()

        relation_rows = [
            {"document_id": document_id, "chunk_id": chunk_ids[r.chunk_index] if r.chunk_index < len(chunk_ids) else None,
             "source_id": ids[r.source], "target_id": ids[r.target], "predicate": r.predicate[:60]}
            for r in relations if r.source in ids and r.target in ids
        ]
        if relation_rows:
            await session.execute(insert(Relation).values(relation_rows).on_conflict_do_nothing())

    await delete_orphan_entities(session, user_id)


async def _join_library_aliases(
    session: AsyncSession, user_id: int, entities: dict[str, Entity], relations: list[ExtractedRelation],
) -> tuple[dict[str, Entity], list[ExtractedRelation]]:
    """Map names to entities already in the library under a longer or shorter form.

    "Northwind" in one document and "Northwind Supply" in another become one entity when exactly
    one existing name matches by whole-word prefix; ambiguous names are left as they are.
    """
    existing = set((await session.execute(select(EntityRow.canonical).where(EntityRow.user_id == user_id))).scalars())
    mapping: dict[str, str] = {}
    for key in entities:
        if key in existing:
            continue
        matches = [e for e in existing if e.startswith(key + " ") or key.startswith(e + " ")]
        if len(matches) == 1:
            mapping[key] = matches[0]
    if not mapping:
        return entities, relations

    joined: dict[str, Entity] = {}
    for key, entity in entities.items():
        target = mapping.get(key, key)
        if target not in joined:
            joined[target] = Entity(target, entity.name, entity.type, {}, entity.type_confirmed)
        for chunk, count in entity.mentions.items():
            joined[target].mentions[chunk] = joined[target].mentions.get(chunk, 0) + count
    joined_relations = [
        ExtractedRelation(mapping.get(r.source, r.source), mapping.get(r.target, r.target), r.predicate, r.chunk_index)
        for r in relations
        if mapping.get(r.source, r.source) != mapping.get(r.target, r.target)
    ]
    return joined, joined_relations


async def delete_orphan_entities(session: AsyncSession, user_id: int) -> None:
    """Entities no longer mentioned by any document (after a delete or a reprocess)."""
    await session.execute(
        delete(EntityRow).where(
            EntityRow.user_id == user_id,
            ~exists(select(EntityMention.entity_id).where(EntityMention.entity_id == EntityRow.id)),
        )
    )
