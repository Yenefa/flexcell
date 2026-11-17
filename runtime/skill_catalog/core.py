"""Load and query a declared action-skill catalog.

Design rules (from the handoff document):

- pure Python, importable without ROS;
- load/query never mutate the caller's data or the catalog file;
- states and availability are returned VERBATIM -- joining a catalog does not
  make a skill callable, validated, or default-enabled;
- malformed input produces an explicit error, never a guessed value.
"""
import copy
import hashlib
import json
import math
from pathlib import Path

SUPPORTED_SCHEMA = "skill-catalog/1"
IMPLEMENTATION_STATES = {"IMPLEMENTED", "PROPOSED", "UNKNOWN"}
AVAILABILITIES = {"OPT_IN", "UNAVAILABLE", "UNKNOWN"}
UNKNOWN = "UNKNOWN"

REQUIRED_FIELDS = (
    "id", "kind", "interface", "implementation_state", "availability",
    "default_enabled", "parameter_constraints", "preconditions",
    "limitations", "validation",
)
REQUIRED_CONTAINERS = ("parameter_constraints", "validation")


class CatalogError(ValueError):
    """JSON, structure or version problem: CLI exit 2."""


class SkillNotFound(KeyError):
    """No such ID in a valid catalog: CLI exit 1."""


def sha256_file(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def _reject_constant(text):
    raise CatalogError("non-finite JSON number is not allowed: %s" % text)


def _check_finite(value, where):
    if isinstance(value, float) and not math.isfinite(value):
        raise CatalogError("non-finite number at %s" % where)
    if isinstance(value, dict):
        for key, item in value.items():
            _check_finite(item, "%s.%s" % (where, key))
    elif isinstance(value, list):
        for number, item in enumerate(value):
            _check_finite(item, "%s[%d]" % (where, number))


def _validation(doc, index):
    section = doc.get("validation")
    if not isinstance(section, dict):
        raise CatalogError("skill[%d].validation must be an object" % index)
    result = dict(section)
    for key in ("level", "executed_source_commit", "evidence_ref"):
        value = result.get(key)
        if value is None or value == "":
            result[key] = UNKNOWN
        elif not isinstance(value, str):
            raise CatalogError("skill[%d].validation.%s must be a string"
                               % (index, key))
    return result


def _validate_skill(doc, index):
    if not isinstance(doc, dict):
        raise CatalogError("skill[%d] must be an object" % index)
    missing = [name for name in REQUIRED_FIELDS if name not in doc]
    if missing:
        raise CatalogError("skill[%d] missing required field(s): %s"
                           % (index, ", ".join(missing)))
    for name in REQUIRED_CONTAINERS:
        if not isinstance(doc[name], dict):
            raise CatalogError("skill[%d].%s must be an object" % (index, name))
    for name in ("preconditions", "limitations"):
        if not isinstance(doc[name], list):
            raise CatalogError("skill[%d].%s must be a list" % (index, name))
    for name in ("id", "kind", "interface"):
        if not isinstance(doc[name], str) or not doc[name]:
            raise CatalogError("skill[%d].%s must be a non-empty string"
                               % (index, name))
    state = doc["implementation_state"]
    if state not in IMPLEMENTATION_STATES:
        raise CatalogError("skill[%d].implementation_state unsupported: %r"
                           % (index, state))
    availability = doc["availability"]
    if availability not in AVAILABILITIES:
        raise CatalogError("skill[%d].availability unsupported: %r"
                           % (index, availability))
    if not isinstance(doc["default_enabled"], bool):
        raise CatalogError("skill[%d].default_enabled must be a boolean"
                           % index)
    cleaned = copy.deepcopy(doc)
    cleaned["validation"] = _validation(doc, index)
    return cleaned


def load_catalog(path):
    """Read and validate a catalog file. Return a detached top-level dict."""
    path = Path(path)
    if not path.is_file():
        raise CatalogError("catalog not found: %s" % path)
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise CatalogError("cannot read catalog %s: %s" % (path, exc)) from exc
    try:
        doc = json.loads(text, parse_constant=_reject_constant)
    except CatalogError:
        raise
    except ValueError as exc:
        raise CatalogError("invalid JSON in %s: %s" % (path, exc)) from exc
    if not isinstance(doc, dict):
        raise CatalogError("catalog root must be a JSON object")
    version = doc.get("schema_version")
    if version != SUPPORTED_SCHEMA:
        raise CatalogError("unsupported schema_version: %r (expected %s)"
                           % (version, SUPPORTED_SCHEMA))
    _check_finite(doc, "catalog")
    skills = doc.get("skills")
    if not isinstance(skills, list):
        raise CatalogError("catalog.skills must be a list")
    seen = set()
    cleaned = []
    for index, item in enumerate(skills):
        skill = _validate_skill(item, index)
        if skill["id"] in seen:
            raise CatalogError("duplicate skill id: %s" % skill["id"])
        seen.add(skill["id"])
        cleaned.append(skill)
    return {"schema_version": version, "skills": cleaned}


def list_skills(catalog):
    """Return an independent list of declared skills. Empty stays empty."""
    return copy.deepcopy(catalog["skills"])


def get_skill(catalog, skill_id):
    """Return an independent record or raise SkillNotFound."""
    for skill in catalog["skills"]:
        if skill["id"] == skill_id:
            return copy.deepcopy(skill)
    raise SkillNotFound(skill_id)
