import spacy

nlp = spacy.load("en_core_web_sm")

def extract_entities(text: str) -> list:
    if len(text) > 5000:
        text = text[:5000]
    
    doc = nlp(text)
    
    entities = []
    for ent in doc.ents:
        entities.append({
            "text": ent.text,
            "label": ent.label_,
            "description": spacy.explain(ent.label_)
        })
    
    return entities