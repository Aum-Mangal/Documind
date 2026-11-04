"""Named entities for the knowledge graph: find them, normalise names, merge aliases, vote on types."""
import re
from collections import Counter, defaultdict
from collections.abc import Iterable
from dataclasses import dataclass, field

from app.services.ner import get_nlp

# spaCy labels worth a node in the graph, mapped to the types the app shows. Dates, amounts,
# percentages and other numbers are left out: they connect everything to everything.
SPACY_TYPES = {
    "PERSON": "PERSON",
    "ORG": "ORG",
    "GPE": "PLACE",
    "LOC": "PLACE",
    "FAC": "PLACE",
    "PRODUCT": "PRODUCT",
    "EVENT": "EVENT",
    "NORP": "GROUP",
    "WORK_OF_ART": "WORK",
    "LAW": "WORK",
}
TYPES = ("PERSON", "ORG", "PLACE", "PRODUCT", "EVENT", "GROUP", "WORK", "OTHER")

_LEADING_ARTICLE = re.compile(r"^(the|a|an)\s+", re.I)
_HONORIFIC = re.compile(r"^(mr|mrs|ms|miss|dr|prof|sir|dame)\.?\s+", re.I)
_POSSESSIVE = re.compile(r"['’]s$")
_EDGE_PUNCT = re.compile(r"^[^\w&]+|[^\w&.]+$")
_NON_WORD = re.compile(r"[^\w&]+")
_STOP_NAMES = {"the", "this", "that", "these", "those", "it", "we", "you", "he", "she", "they"}


def display_name(surface: str) -> str:
    name = " ".join(surface.split())
    name = _LEADING_ARTICLE.sub("", name)
    name = _HONORIFIC.sub("", name)
    name = _POSSESSIVE.sub("", name)
    return _EDGE_PUNCT.sub("", name).strip()


def canonical(name: str) -> str:
    """The key two spellings of the same entity share: case, punctuation and spacing removed."""
    return " ".join(_NON_WORD.sub(" ", display_name(name).lower()).split())


def text_key(text: str) -> str:
    """The same normalisation applied to free text (a question), padded so names match whole words."""
    return f" {' '.join(_NON_WORD.sub(' ', text.lower()).split())} "


def _usable(name: str, key: str) -> bool:
    return len(key) >= 2 and key not in _STOP_NAMES and not key.replace(" ", "").isdigit()


@dataclass
class Entity:
    key: str
    name: str
    type: str
    # chunk index -> mentions in that chunk
    mentions: dict[int, int] = field(default_factory=dict)
    # True once the LLM has confirmed or corrected the type
    type_confirmed: bool = False

    @property
    def total(self) -> int:
        return sum(self.mentions.values())


def extract(chunks: list[str]) -> dict[str, Entity]:
    """Entities in a document's chunks, keyed by canonical name, after alias merging."""
    surfaces: dict[str, Counter] = defaultdict(Counter)   # key -> surface spellings
    labels: dict[str, Counter] = defaultdict(Counter)     # key -> type votes
    mentions: dict[str, Counter] = defaultdict(Counter)   # key -> chunk index counts

    for index, doc in enumerate(get_nlp().pipe(chunks, batch_size=16)):
        for ent in doc.ents:
            kind = SPACY_TYPES.get(ent.label_)
            if kind is None:
                continue
            name = display_name(ent.text)
            key = canonical(name)
            if not _usable(name, key):
                continue
            surfaces[key][name] += 1
            labels[key][kind] += 1
            mentions[key][index] += 1

    entities = {
        key: Entity(key, surfaces[key].most_common(1)[0][0], labels[key].most_common(1)[0][0], dict(mentions[key]))
        for key in mentions
    }
    return merge_aliases(entities)


def merge_aliases(entities: dict[str, Entity]) -> dict[str, Entity]:
    """Merge names where one is a whole-word prefix of another ("Northwind" / "Northwind Supply").

    The more frequently mentioned form wins (the shorter on a tie), so a stray long phrase like
    "Halden & Rowe Quarterly Report" folds into "Halden & Rowe" rather than the other way round.
    """
    keys = sorted(entities, key=len)
    target: dict[str, str] = {}
    for i, short in enumerate(keys):
        for long in keys[i + 1:]:
            if long.startswith(short + " "):
                a, b = entities[short], entities[long]
                winner = short if a.total >= b.total else long
                loser = long if winner == short else short
                target.setdefault(loser, winner)
    # A lone surname ("Okafor", once "Ms Okafor") is the person whose full name ends with it,
    # when exactly one such person is mentioned
    for short in keys:
        if " " in short or short in target:
            continue
        people = [k for k in keys if k != short and k.endswith(" " + short) and entities[k].type == "PERSON"]
        if len(people) == 1:
            target[short] = people[0]

    def resolve(key: str) -> str:
        seen = set()
        while key in target and key not in seen:
            seen.add(key)
            key = target[key]
        return key

    merged: dict[str, Entity] = {}
    votes: dict[str, Counter] = defaultdict(Counter)
    for key, entity in entities.items():
        root = resolve(key)
        votes[root][entity.type] += entity.total
        if root not in merged:
            base = entities[root]
            merged[root] = Entity(root, base.name, base.type, {})
        for chunk, count in entity.mentions.items():
            merged[root].mentions[chunk] = merged[root].mentions.get(chunk, 0) + count
    for root, entity in merged.items():
        entity.type = votes[root].most_common(1)[0][0]
    return merged


def names_in(text: str, entities: Iterable[Entity]) -> list[Entity]:
    """Entities whose name appears, as whole words, in the text."""
    haystack = text_key(text)
    return [e for e in entities if f" {e.key} " in haystack]
