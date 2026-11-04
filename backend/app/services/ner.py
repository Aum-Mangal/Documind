import spacy

_nlp = None


def get_nlp():
    """The spaCy English pipeline, loaded once. Only the parts NER needs are kept."""
    global _nlp
    if _nlp is None:
        _nlp = spacy.load("en_core_web_sm", exclude=["lemmatizer"])
    return _nlp
