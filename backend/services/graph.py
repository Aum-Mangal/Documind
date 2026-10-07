from collections import defaultdict
from services.ner import get_nlp

def generate_document_graph(raw_text: str, max_nodes: int = 50) -> dict:
    """
    Extracts entities and computes co-occurrence relationships within a document.
    Returns { "nodes": [...], "edges": [...] } ready for Cytoscape.js visualization.
    """
    if not raw_text or len(raw_text.strip()) < 10:
        return {"nodes": [], "edges": []}

    nlp = get_nlp()
    # Process text in sections / paragraphs to capture local co-occurrences
    paragraphs = [p.strip() for p in raw_text.split("\n\n") if len(p.strip()) > 20]
    if not paragraphs:
        paragraphs = [raw_text[:3000]]

    entity_counts = defaultdict(int)
    entity_types = {}
    co_occurrences = defaultdict(int)

    for p in paragraphs[:30]:  # limit to top paragraphs for fast execution
        doc = nlp(p)
        ents_in_p = []
        for ent in doc.ents:
            cleaned = ent.text.strip()
            if len(cleaned) < 2 or cleaned.lower() in ["the", "this", "that"]:
                continue
            entity_counts[cleaned] += 1
            entity_types[cleaned] = ent.label_
            ents_in_p.append(cleaned)

        # Unique entities in paragraph
        unique_ents = list(set(ents_in_p))
        for i in range(len(unique_ents)):
            for j in range(i + 1, len(unique_ents)):
                pair = tuple(sorted([unique_ents[i], unique_ents[j]]))
                co_occurrences[pair] += 1

    # Select top entities by frequency
    sorted_entities = sorted(entity_counts.items(), key=lambda x: x[1], reverse=True)[:max_nodes]
    selected_entity_names = set(k for k, _ in sorted_entities)

    nodes = []
    degree_counts = defaultdict(int)

    # Filter edges between selected entities
    edges = []
    for (src, tgt), count in co_occurrences.items():
        if src in selected_entity_names and tgt in selected_entity_names:
            degree_counts[src] += 1
            degree_counts[tgt] += 1
            edges.append({
                "source": src,
                "target": tgt,
                "weight": count,
                "label": "COOCCURS_WITH"
            })

    for name, count in sorted_entities:
        nodes.append({
            "id": name,
            "label": name,
            "type": entity_types.get(name, "OTHER"),
            "weight": count,
            "degree": degree_counts[name]
        })

    return {
        "nodes": nodes,
        "edges": edges
    }

def generate_global_graph(documents: list, max_nodes: int = 80) -> dict:
    """
    Builds a global cross-document knowledge network linking entities across files.
    """
    nlp = get_nlp()
    entity_doc_map = defaultdict(set)
    entity_types = {}
    entity_counts = defaultdict(int)
    co_occurrences = defaultdict(int)

    for d in documents[:25]:
        text = d.raw_text or ""
        doc = nlp(text[:2500])
        doc_ents = []
        for ent in doc.ents:
            cleaned = ent.text.strip()
            if len(cleaned) < 2 or cleaned.lower() in ["the", "this", "that"]:
                continue
            entity_counts[cleaned] += 1
            entity_types[cleaned] = ent.label_
            entity_doc_map[cleaned].add(d.filename)
            doc_ents.append(cleaned)

        unique_ents = list(set(doc_ents))
        for i in range(len(unique_ents)):
            for j in range(i + 1, len(unique_ents)):
                pair = tuple(sorted([unique_ents[i], unique_ents[j]]))
                co_occurrences[pair] += 1

    sorted_entities = sorted(entity_counts.items(), key=lambda x: x[1], reverse=True)[:max_nodes]
    selected_entity_names = set(k for k, _ in sorted_entities)

    degree_counts = defaultdict(int)
    edges = []
    for (src, tgt), count in co_occurrences.items():
        if src in selected_entity_names and tgt in selected_entity_names:
            degree_counts[src] += 1
            degree_counts[tgt] += 1
            edges.append({
                "source": src,
                "target": tgt,
                "weight": count,
                "label": "COOCCURS_WITH"
            })

    nodes = []
    for name, count in sorted_entities:
        nodes.append({
            "id": name,
            "label": name,
            "type": entity_types.get(name, "OTHER"),
            "weight": count,
            "degree": degree_counts[name],
            "doc_count": len(entity_doc_map[name])
        })

    return {
        "nodes": nodes,
        "edges": edges
    }
