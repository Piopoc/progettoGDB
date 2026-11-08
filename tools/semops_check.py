#!/usr/bin/env python3
"""Checker of the run files of the team project on semantic operators.

Graph Databases, University of Padua, A.Y. 2026/2027.

A run file holds one run of one query in one JSON object. It records the answer of the run in the
SPARQL 1.1 Query Results JSON Format, the model calls of the run as the gateway logged them, and the
price list that prices those calls. This module validates run files, computes the metrics of every run
and writes the results table. Students run it on their repository before they submit. The grader of the
instructor, semops_grade.py, imports it, so both compute every number with the same code.

Repository layout
  runs/<domain>/<data_set>/<query_id>/<run_id>.json    one run file per run
  keys/<domain>/<data_set>/<query_id>/key.json         the answer key of each own query, one per set

Usage
  python3 semops_check.py <repository root or run files> [--data films=<package> games=<package>]
                          [--keys <directory>] [--prices <price list>] [--results <results.csv>]

  --data      data packages, one per domain; the checker reads gt/, sets.csv and entities.csv of each set
  --keys      a directory of published answer keys with the layout of keys/, for pool queries
  --prices    an official price list, which adds the column cost_official
  --results   write the results table, one row per usable run, to this CSV file

The checker prints the errors and warnings of every file, then one summary line per usable run. It exits
with status 1 when any file has an error. An error makes a file unusable, and a warning names something
to verify. The effectiveness metrics of a common query need the data package of its domain.

Library functions for students
  calls_from_log(log_path, run_id)   the call records of one run, read from the JSON lines of the gateway log
  write_run_file(repo_root, doc)     validates a run file and writes it to its path in the repository
"""
import argparse
import csv
import json
import math
import os
import re
import sys
from collections import Counter, OrderedDict, defaultdict, namedtuple
from datetime import datetime, timezone

FORMAT = "semops-run/1"
WD = "http://www.wikidata.org/entity/"

KIND = {"Q1": "filter", "Q2": "filter", "Q3": "filter", "Q4": "classify", "Q5": "extract",
        "Q6": "join", "Q7": "join", "Q8": "count"}
ARITY = {"filter": 1, "classify": 2, "extract": 2, "join": 2, "count": 2}
OPERATOR = {"Q1": "sem_filter", "Q2": "sem_filter", "Q3": "sem_filter", "Q4": "sem_classify", "Q5": "sem_map",
            "Q6": "sem_join", "Q7": "sem_join", "Q8": "sem_filter"}
MANDATORY = ("Q1", "Q2", "Q3", "Q4", "Q5", "Q6", "Q8")  # Q7 optional since 2026-11-04
DOMAINS = ("films", "games")
DATA_SETS = ("dev", "eval")
QUERY_SETS = ("common", "own", "pool")
POOL_MODES = ("as-is", "recalibrated")
ENDPOINTS = ("responses", "embeddings")

# The language expressions and label sets of the query reference (2026_semantic-operators-team-project_query-set).
LANGEX = {
    "films": {"Q1": "the film deals with the Second World War", "Q2": "the film deals with time travel",
              "Q4": "the genre that describes the film best",
              "Q5": "the main place where the story of the film is set", "Q6": "the film is based on the novel"},
    "games": {"Q1": "the game is a platformer", "Q2": "the game is a visual novel",
              "Q4": "the genre that describes the game best", "Q5": "the company that developed the game",
              "Q6": "the game is part of the series"},
}
for _langex in LANGEX.values():
    _langex["Q3"] = _langex["Q8"] = _langex["Q1"]
    _langex["Q7"] = _langex["Q6"]
LABEL_SET = {
    "films": {"Q130232": "drama film", "Q93204": "documentary film", "Q369747": "war film",
              "Q188473": "action film", "Q157443": "comedy film", "Q2484376": "thriller film",
              "Q200092": "horror film", "Q471839": "science fiction film"},
    "games": {"Q270948": "action game", "Q23916": "adventure video game", "Q744038": "role-playing video game",
              "Q343568": "action-adventure game", "Q54767": "puzzle video game", "Q860750": "racing video game",
              "Q185029": "first-person shooter", "Q1044478": "shoot 'em up"},
}

TOP_FIELDS = ("format", "run", "answer", "candidates", "oracle_check", "calls", "price_list")
RUN_FIELDS = OrderedDict([
    ("group_id", "str"), ("domain", "str"), ("data_set", "str"), ("query_set", "str"), ("query_id", "str"),
    ("run_id", "str"), ("plan_id", "str"), ("plan_params", "object"), ("reference_run_id", "str?"),
    ("source_run_id", "str?"), ("engine", "str"), ("model_oracle", "str"), ("model_proxy", "str?"),
    ("language_expression", "str"), ("labels", "list?"), ("n_input_bindings", "int"), ("sample", "object?"),
    ("pool_mode", "str?"), ("shipped", "bool"), ("started_at", "str"), ("finished_at", "str"),
    ("wallclock_s", "number"),
])
CALL_FIELDS = OrderedDict([
    ("ts", "number"), ("endpoint", "str"), ("key", "str"), ("model", "str"), ("cache_hit", "bool"),
    ("parse_ok", "bool"), ("tokens_in", "int"), ("tokens_out", "int"), ("latency_s", "number"),
])
TYPE_NAMES = {"str": "a non-empty string", "int": "an integer", "number": "a number", "bool": "true or false",
              "object": "a JSON object", "list": "a JSON array"}

# Roles of the variables of a result set. An entity is a Wikidata IRI or a literal holding a Q-id.
# "?" allows an unbound variable; "group" and "count" allow it too but ignore the solution, as the scorer does.
ANSWER_ROLES = {"filter": ("entity",), "classify": ("entity", "term?"), "extract": ("entity", "entity?"),
                "join": ("entity", "entity"), "count": ("group", "count")}
ANSWER_VARS = {"filter": "entity", "classify": "entity, label", "extract": "entity, value", "join": "left, right",
               "count": "group, count"}
KEY_ROLES = {"filter": ("entity",), "classify": ("entity", "term"), "join": ("entity", "entity"),
             "count": ("entity", "term")}
KEY_VARS = {"filter": "entity", "classify": "entity, label", "join": "left, right", "count": "entity, group"}

GROUP_ID = re.compile(r"^g\d{2}$")
COMMON_ID = re.compile(r"^Q[1-8]$")
GROUP_QUERY_ID = re.compile(r"^(g\d{2})-(Q[1-8])$")
RUN_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
KEY_HEX = re.compile(r"^[0-9a-fA-F]{64}$")
QID = re.compile(r"^Q[1-9][0-9]*$")
UTC_TIME = re.compile(r"^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})(\.\d+)?(Z|\+00:00)$")

TIME_SLACK_S = 5.0   # calls may lie this far outside [started_at, finished_at] before a warning
MIN_ORACLE_CHECKS = 100

RESULT_COLUMNS = [
    "group_id", "domain", "data_set", "query_set", "query_id", "operator", "run_id",
    "plan_id", "plan_params", "model_oracle", "model_proxy",
    "n_input_bindings", "n_function_calls", "n_llm_calls", "tokens_in", "tokens_out", "wallclock_s", "cost",
    "price_list_id", "cache_hit_rate",
    "precision_gt", "recall_gt", "f1_gt", "hit_rate", "accuracy", "macro_f1", "rel_error", "spearman",
    "precision_ref", "recall_ref", "f1_ref", "accuracy_ref",
    "blocking_recall", "oracle_fraction", "unresolved_rate",
    "parse_failures",
]
EXTRA_COLUMNS = [
    "precision_direct", "recall_direct", "f1_direct", "recall_wilson_low", "recall_wilson_high",
    "n_key", "n_answer_rows", "outside_inputs", "outside_restriction", "outside_L", "missing",
    "n_candidates", "outside_candidates",
    "oracle_checks", "oracle_agreement", "oracle_agreement_low", "oracle_agreement_high",
    "zero_groups_predicted", "groups_outside_key",
    "calls_per_input", "llm_calls_per_input", "n_embedding_requests", "embedding_tokens",
    "cost_paid", "cost_official", "currency", "official_price_list_id",
    "model_seconds", "latency_median_s", "latency_p95_s",
    "shipped", "reference_run_id", "source_run_id", "sample_method", "sample_size", "pool_mode", "engine",
]

Diagnostic = namedtuple("Diagnostic", "level path message")


class RunFileError(Exception):
    """Raised by write_run_file when a run file has errors. The attribute errors lists them."""

    def __init__(self, errors):
        self.errors = list(errors)
        Exception.__init__(self, "the run file has %d error(s)\n  " % len(self.errors) + "\n  ".join(self.errors))


# ---------------------------------------------------------------------------------------------------------
# Values. These functions come from tools/semops_eval.py of the data packages, verified on 2026-09-21.
# ---------------------------------------------------------------------------------------------------------

def value(term):
    """The comparable form of an RDF term. A Wikidata IRI becomes its identifier, a literal keeps its value."""
    v = str(term.get("value", "")).strip()
    if term.get("type") == "uri" and v.startswith(WD):
        return v[len(WD):]
    return v


def group(x):
    """A group. An integral number becomes an integer string, so that 1940, "1940" and "1940.0" agree."""
    try:
        f = float(x)
        return str(int(f)) if f == int(f) else str(f)
    except (TypeError, ValueError, OverflowError):
        return str(x).strip()


def local_name(run_id):
    """The local name of a run identifier given as an IRI, a prefixed name or a plain name."""
    return run_id.strip().rstrip("/").rsplit("/", 1)[-1].rsplit("#", 1)[-1].rsplit(":", 1)[-1]


def entity_of(term):
    """The Q-id of an entity term, or None when the term is neither a Wikidata IRI nor a literal holding a Q-id."""
    if not isinstance(term, dict) or not isinstance(term.get("value"), str):
        return None
    v = term["value"].strip()
    if term.get("type") == "uri":
        return v[len(WD):] if v.startswith(WD) and QID.match(v[len(WD):]) else None
    if term.get("type") == "literal":
        return v if QID.match(v) else None
    return None


def entity_string(x):
    """The Q-id of a string that holds a Q-id or a Wikidata IRI, or None."""
    if not isinstance(x, str):
        return None
    x = x.strip()
    if x.startswith(WD):
        x = x[len(WD):]
    return x if QID.match(x) else None


def qtype(query_id):
    """Q1 to Q8 for a common query, and the type after the hyphen for an own or pool query such as g07-Q2."""
    return query_id.strip().rsplit("-", 1)[-1]


# ---------------------------------------------------------------------------------------------------------
# Effectiveness. prf, wilson, labels_of, score_filter, score_extract, pairs, score_join and score_count are
# those of tools/semops_eval.py. score_classify takes the label set L as an argument, so that a restricted
# key keeps the label set of the full key, and its macro-F1 averages over the labels that are the true or the
# predicted label of at least one single-label input. On the common Q4 of the four released sets every label
# of L is the true label of some single-label input, so the result equals that of semops_eval.py.
# ---------------------------------------------------------------------------------------------------------

def prf(pred, gold):
    tp = len(pred & gold)
    if not pred and not gold:
        return dict(precision=None, recall=None, f1=1.0, tp=0, n_pred=0, n_gold=0)
    p = tp / len(pred) if pred else None
    r = tp / len(gold) if gold else None
    f = 0.0 if (not pred or not gold or tp == 0) else 2 * p * r / (p + r)
    return dict(precision=p, recall=r, f1=f, tp=tp, n_pred=len(pred), n_gold=len(gold))


def wilson(k, n, z=1.96):
    if n == 0:
        return (None, None)
    p = k / n
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return ((c - h) / d, (c + h) / d)


def score_filter(key, rows, ref=None):
    pred = {r[0] for r in rows if r[0]}
    out = dict(n_solutions=len(rows), n_entities=len(pred))
    if key["inputs"] is not None:
        out["n_inputs"] = len(key["inputs"])
        out["outside_inputs"] = len(pred - key["inputs"])
    out["gt"] = prf(pred, key["gold"])
    out["gt"]["recall_wilson95"] = wilson(out["gt"]["tp"], len(key["gold"]))
    if key["direct"] is not None:
        out["gt_direct"] = prf(pred, key["direct"])
    if ref is not None:
        out["reference"] = prf(pred, {r[0] for r in ref if r[0]})
    return out


def labels_of(rows, names):
    """One label per entity; an entity with two different labels has none."""
    pred, conflicts = {}, set()
    for e, l in rows:
        if not e:
            continue
        if l is not None:
            l = names.get(l.lower(), l)
        if e in pred and pred[e] != l:
            conflicts.add(e)
        pred.setdefault(e, l)
    for e in conflicts:
        pred[e] = None
    return pred, conflicts


def score_classify(key, rows, ref=None, labels=None):
    gold, names = key["gold"], key["names"]
    if labels is None:
        labels = set().union(*gold.values()) if gold else set()
    pred, conflicts = labels_of(rows, names)
    single = {e: next(iter(ls)) for e, ls in gold.items() if len(ls) == 1}
    f1s = []
    for l in sorted(labels):
        tp = sum(1 for e, g in single.items() if g == l and pred.get(e) == l)
        fp = sum(1 for e, g in single.items() if g != l and pred.get(e) == l)
        fn = sum(1 for e, g in single.items() if g == l and pred.get(e) != l)
        if tp + fp + fn == 0:
            continue                # l is neither the true nor the predicted label of a single-label input
        f1s.append(0.0 if tp == 0 else 2 * tp / (2 * tp + fp + fn))
    n = len(gold)
    out = dict(n_inputs=n, n_single=len(single), n_solutions=len(rows),
               hit_rate=sum(1 for e, ls in gold.items() if pred.get(e) in ls) / n if n else None,
               accuracy=sum(1 for e, l in single.items() if pred.get(e) == l) / len(single) if single else None,
               macro_f1=sum(f1s) / len(f1s) if f1s else None,
               outside_L=sum(1 for e in gold if pred.get(e) is not None and pred[e] not in labels),
               unbound=sum(1 for e in gold if e in pred and pred[e] is None and e not in conflicts),
               conflicting=len(conflicts & set(gold)), missing=len(set(gold) - set(pred)),
               outside_inputs=len(set(pred) - set(gold)))
    if ref is not None:
        rp, _ = labels_of(ref, names)
        out["accuracy_ref"] = (sum(1 for e in gold if pred.get(e) is not None and pred.get(e) == rp.get(e)) / n
                               if n else None)
    return out


def score_extract(key, rows):
    gold = key["gold"]
    pred = {}
    for e, v in rows:
        if e and e not in pred:
            pred[e] = v
    unresolved = lambda v: v is None or v == "unresolved"
    n = len(gold)
    return dict(n_inputs=n, n_solutions=len(rows),
                accuracy=(sum(1 for e, vs in gold.items() if not unresolved(pred.get(e)) and pred[e] in vs) / n
                          if n else None),
                unresolved_rate=sum(1 for e in gold if unresolved(pred.get(e))) / n if n else None)


def pairs(rows):
    return {(l, r) for l, r in rows if l and r}


def score_join(key, rows, ref=None, cand=None):
    pred, gold = pairs(rows), key["gold"]
    out = dict(n_solutions=len(rows), gt=prf(pred, gold))
    if cand is not None:
        c = pairs(cand)
        out["n_candidates"] = len(c)
        out["blocking_recall"] = len(c & gold) / len(gold) if gold else None
        out["outside_candidates"] = len(pred - c)
    if ref is not None:
        out["reference"] = prf(pred, pairs(ref))
    return out


def score_count(key, rows):
    gold = key["gold"]
    pred, duplicates = {}, 0
    for g, c in rows:
        if g is None or c is None:
            continue
        g = group(g)
        duplicates += g in pred
        pred[g] = float(c)
    errs = [abs(pred.get(g, 0.0) - t) / t for g, t in gold.items() if t > 0]
    return dict(n_solutions=len(rows), n_groups=len(errs), duplicate_groups=duplicates,
                mare=sum(errs) / len(errs) if errs else None,
                zero_groups_predicted={g: pred.get(g, 0.0) for g, t in gold.items() if t == 0},
                groups_outside_key={g: c for g, c in pred.items() if g not in gold})


def nearest_rank(sorted_values, p):
    """The p-th percentile of sorted values by the nearest-rank method, the value of rank ceil(p n / 100)."""
    if not sorted_values:
        return None
    rank = max(1, (p * len(sorted_values) + 99) // 100)
    return sorted_values[rank - 1]


# ---------------------------------------------------------------------------------------------------------
# Reading files
# ---------------------------------------------------------------------------------------------------------

def _reject_constant(name):
    raise ValueError("%s is not a JSON number" % name)


def read_json(path):
    """The parsed content of a JSON file. Raises ValueError with a readable message."""
    try:
        with open(path, encoding="utf-8") as f:
            text = f.read()
    except UnicodeDecodeError:
        raise ValueError("the file is not UTF-8 text")
    try:
        return json.loads(text, parse_constant=_reject_constant)
    except json.JSONDecodeError as e:
        raise ValueError("invalid JSON, line %d column %d, %s" % (e.lineno, e.colno, e.msg))


def read_csv(path):
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _raise_csv_limit():
    limit = sys.maxsize
    while True:
        try:
            csv.field_size_limit(limit)
            return
        except OverflowError:
            limit //= 10


_raise_csv_limit()


# ---------------------------------------------------------------------------------------------------------
# Validation of one run file
# ---------------------------------------------------------------------------------------------------------

def _show(x, width=60):
    s = json.dumps(x, ensure_ascii=False)
    return s if len(s) <= width else s[:width - 3] + "..."


def _jtype(x):
    return {dict: "an object", list: "an array", str: "a string", bool: "a Boolean", type(None): "null"}.get(
        type(x), "a number")


def _type_ok(x, typ):
    if x is None:
        return typ.endswith("?")
    t = typ.rstrip("?")
    if t == "str":
        return isinstance(x, str) and x.strip() != ""
    if t == "int":
        return isinstance(x, int) and not isinstance(x, bool)
    if t == "number":
        return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x)
    if t == "bool":
        return isinstance(x, bool)
    if t == "object":
        return isinstance(x, dict)
    if t == "list":
        return isinstance(x, list)
    return False


def _type_name(typ):
    return TYPE_NAMES[typ.rstrip("?")] + (" or null" if typ.endswith("?") else "")


def parse_utc(s):
    """Seconds since the Unix epoch of an ISO 8601 UTC time such as 2026-12-15T10:00:00Z, or None."""
    m = UTC_TIME.match(s) if isinstance(s, str) else None
    if not m:
        return None
    try:
        t = datetime(*[int(x) for x in m.groups()[:6]], tzinfo=timezone.utc)
    except ValueError:
        return None
    return t.timestamp() + float(m.group(7) or 0)


class _Tally:
    """Collects repeated problems so that a message appears once, with its count and its first place."""

    def __init__(self):
        self.items = OrderedDict()

    def add(self, message, where):
        if message in self.items:
            self.items[message][0] += 1
        else:
            self.items[message] = [1, where]

    def emit(self, report):
        for message, (n, where) in self.items.items():
            report("%s (%s)" % (message, "at " + where if n == 1 else "%d times, first at %s" % (n, where)))


def check_result_set(obj, name, roles, err, warn):
    """Checks a result set of the SPARQL 1.1 Query Results JSON Format.

    roles gives the role of each variable in order, or None to check the structure only. The function
    returns the solutions as tuples of comparable values, with None for an unbound variable, or None when
    the structure is broken. An entity becomes its Q-id.
    """
    if not isinstance(obj, dict):
        err("%s must be a result set of the SPARQL 1.1 Query Results JSON Format, an object with head.vars and "
            "results.bindings" % name)
        return None
    head, results = obj.get("head"), obj.get("results")
    names = head.get("vars") if isinstance(head, dict) else None
    bindings = results.get("bindings") if isinstance(results, dict) else None
    if not isinstance(names, list) or not all(isinstance(v, str) and v for v in names) or len(set(names)) != len(names):
        err("%s.head.vars must be an array of distinct variable names" % name)
        return None
    if not isinstance(bindings, list):
        err("%s.results.bindings must be an array of solutions" % name)
        return None
    if roles is not None and len(names) != len(roles):
        err("%s has %d variable(s) %s, and this query type needs %d" % (name, len(names), _show(names), len(roles)))
        return None
    errors, ignored = _Tally(), _Tally()
    rows = []
    for i, b in enumerate(bindings):
        where = "solution %d" % i
        if not isinstance(b, dict):
            errors.add("a solution is not a JSON object", where)
            continue
        if any(k not in names for k in b):
            errors.add("a solution binds a variable that is not in head.vars", where)
        row = []
        for j, var in enumerate(names):
            role = roles[j] if roles is not None else "term?"
            term = b.get(var)
            if term is None:
                row.append(None)
                if role in ("entity", "term"):
                    errors.add("variable %s is unbound" % var, where)
                elif role in ("group", "count"):
                    ignored.add("%s ignores solutions that leave the group or the count unbound" % name, where)
                continue
            if not (isinstance(term, dict) and term.get("type") in ("uri", "literal", "bnode")
                    and isinstance(term.get("value"), str)):
                errors.add("variable %s holds something that is not an RDF term of the format" % var, where)
                row.append(None)
                continue
            if role.startswith("entity"):
                q = entity_of(term)
                if q is None:
                    errors.add("variable %s holds a value that is neither a Wikidata IRI nor a Q-id" % var,
                               "%s, %s" % (where, _show(term.get("value"), 50)))
                row.append(q)
            elif role == "count":
                v = value(term)
                try:
                    ok = math.isfinite(float(v))
                except ValueError:
                    ok = False
                if not ok:
                    errors.add("variable %s holds a count that is not a number" % var, where)
                    row.append(None)
                else:
                    row.append(v)
            else:
                row.append(value(term))
        rows.append(tuple(row))
    errors.emit(lambda m: err("%s, %s" % (name, m)))
    ignored.emit(warn)
    return rows


def _empty_info():
    return dict.fromkeys(("group_id", "domain", "data_set", "query_set", "query_id", "run_id", "plan_id", "type",
                          "kind", "started", "finished", "source", "sample", "model_oracle", "model_proxy"))


def _check_run(r, parts, err, warn):
    """Checks the object run and returns what the other checks need, with None for every invalid value."""
    info = _empty_info()
    if not isinstance(r, dict):
        err("run must be a JSON object")
        return info
    for f, typ in RUN_FIELDS.items():
        if f not in r:
            err("run.%s is missing" % f)
        elif not _type_ok(r[f], typ):
            err("run.%s must be %s" % (f, _type_name(typ)))
    for f in r:
        if f not in RUN_FIELDS:
            warn("unknown key run.%s is ignored" % f)

    def get(f):
        x = r.get(f)
        return x if (f in r and _type_ok(x, RUN_FIELDS[f])) else None

    gid, dom, ds, qs, qid, rid = (get(f) for f in ("group_id", "domain", "data_set", "query_set", "query_id",
                                                     "run_id"))
    if gid is not None and not GROUP_ID.match(gid):
        err('run.group_id %s must be g followed by two digits, such as "g07"' % _show(gid))
        gid = None
    for f, allowed in (("domain", DOMAINS), ("data_set", DATA_SETS), ("query_set", QUERY_SETS)):
        if get(f) is not None and get(f) not in allowed:
            err("run.%s %s must be one of %s" % (f, _show(get(f)), ", ".join(allowed)))
    dom = dom if dom in DOMAINS else None
    ds = ds if ds in DATA_SETS else None
    qs = qs if qs in QUERY_SETS else None

    t = None
    if qid is not None:
        m = GROUP_QUERY_ID.match(qid)
        if qs == "common" or (qs is None and not m):
            if COMMON_ID.match(qid):
                t = qid
            else:
                err("run.query_id %s of a common query must be Q1 to Q8" % _show(qid))
        elif not m:
            err('run.query_id %s of an %s query must be <group>-Q<n>, such as "g07-Q2"' % (_show(qid), qs))
        elif m.group(2) == "Q5":
            err("run.query_id %s uses the type Q5; own and pool queries have the types Q1 to Q4 and Q6 to Q8"
                % _show(qid))
        else:
            t = m.group(2)
            if gid is not None and qs == "own" and m.group(1) != gid:
                err("run.query_id %s of an own query must start with the group id %s" % (_show(qid), gid))
            if gid is not None and qs == "pool" and m.group(1) == gid:
                err("run.query_id %s starts with your own group id; a query of your group has query_set own"
                    % _show(qid))
    kind = KIND.get(t)

    if rid is not None and not RUN_ID.match(rid):
        err("run.run_id %s may contain only letters, digits, dots, hyphens and underscores, and starts with a "
            "letter or a digit" % _show(rid))
    if parts is not None:
        pdom, pds, pqid, pname = parts
        for f, have, want in (("domain", pdom, get("domain")), ("data_set", pds, get("data_set")),
                              ("query_id", pqid, qid)):
            if want is not None and have != want:
                err("the file lies in the folder %s, but run.%s is %s" % (have, f, _show(want)))
        if rid is not None and pname != rid + ".json":
            err("the file name %s must be run.run_id followed by .json, %s" % (pname, rid + ".json"))

    pool_mode = r.get("pool_mode")
    if qs == "pool":
        if ds is not None and ds != "eval":
            err("pool runs use the evaluation set, data_set eval")
        if pool_mode not in POOL_MODES:
            err("run.pool_mode of a pool run must be as-is or recalibrated")
    elif qs is not None and pool_mode is not None:
        err("run.pool_mode must be null for a %s run" % qs)

    labels = r.get("labels")
    if kind == "classify":
        if not (isinstance(labels, list) and labels and all(_type_ok(x, "str") for x in labels)):
            err("run.labels of a classification must be the label set as sent, a non-empty array of strings")
    elif kind is not None and labels is not None:
        err("run.labels must be null for a query that is not a classification")

    n = get("n_input_bindings")
    if n is not None and n < 1:
        err("run.n_input_bindings must be at least 1")

    sample = r.get("sample")
    if isinstance(sample, dict):
        inputs = sample.get("inputs")
        if not _type_ok(sample.get("method"), "str"):
            err("run.sample.method must be a non-empty string that names the sampling method")
        if not isinstance(inputs, list) or not inputs:
            err("run.sample.inputs must be a non-empty array of Q-ids")
        else:
            qids = [entity_string(x) for x in inputs]
            if any(q is None for q in qids):
                err("run.sample.inputs holds a value that is neither a Q-id nor a Wikidata IRI, such as %s"
                    % _show(inputs[[q is None for q in qids].index(True)]))
            else:
                info["sample"] = set(qids)

    started, finished = parse_utc(r.get("started_at")), parse_utc(r.get("finished_at"))
    for f, v in (("started_at", started), ("finished_at", finished)):
        if _type_ok(r.get(f), "str") and v is None:
            err("run.%s %s must be an ISO 8601 UTC time, such as 2026-12-15T10:00:00Z" % (f, _show(r[f])))
    wall = get("wallclock_s")
    if wall is not None and wall < 0:
        err("run.wallclock_s must be at least 0")
        wall = None
    if started is not None and finished is not None:
        span = finished - started
        if span < 0:
            warn("run.finished_at precedes run.started_at")
        elif wall is not None and abs(wall - span) > max(TIME_SLACK_S, 0.1 * span):
            warn("run.wallclock_s is %s, while finished_at minus started_at is %.1f s" % (_num(wall), span))

    plan, ref, src = get("plan_id"), get("reference_run_id"), get("source_run_id")
    if plan == "ref" and ref is not None:
        err("run.reference_run_id must be null for a run of the plan ref")
    elif ref is not None and ref == rid:
        err("run.reference_run_id names the run itself")
    if src is not None and src == rid:
        err("run.source_run_id names the run itself")

    le = get("language_expression")
    if qs == "common" and t is not None and dom is not None and le is not None and le.strip() != LANGEX[dom][t]:
        warn('run.language_expression differs from the query reference, which has "%s"' % LANGEX[dom][t])
    if qs == "common" and t == "Q4" and dom is not None and isinstance(labels, list):
        names = {v.lower(): k for k, v in LABEL_SET[dom].items()}
        sent = {names.get(x.strip().lower(), entity_string(x) or x.strip()) for x in labels if isinstance(x, str)}
        want = set(LABEL_SET[dom])
        if sent != want:
            warn("run.labels differs from the label set L of the query reference (%d labels missing, %d extra)"
                 % (len(want - sent), len(sent - want)))

    info.update(group_id=gid, domain=dom, data_set=ds, query_set=qs, query_id=qid if t else None, run_id=rid,
                plan_id=plan, type=t, kind=kind, started=started, finished=finished, source=src is not None,
                model_oracle=get("model_oracle"), model_proxy=get("model_proxy"))
    return info


def _num(x):
    return ("%.4f" % x).rstrip("0").rstrip(".") if isinstance(x, float) else str(x)


def _check_calls(calls, info, err, warn):
    """Checks the call records and returns the valid ones."""
    if not isinstance(calls, list):
        err("calls must be a JSON array")
        return []
    errors = _Tally()
    first, valid = {}, []
    for i, c in enumerate(calls):
        where = "calls[%d]" % i
        if not isinstance(c, dict):
            errors.add("calls, a record is not a JSON object", where)
            continue
        good = True
        for f, typ in CALL_FIELDS.items():
            if f not in c:
                errors.add("calls, a record has no %s" % f, where)
                good = False
            elif not _type_ok(c[f], typ):
                errors.add("calls, %s must be %s" % (f, _type_name(typ)), where)
                good = False
        if not good:
            continue
        if c["endpoint"] not in ENDPOINTS:
            errors.add('calls, endpoint must be "responses" or "embeddings"', where)
            good = False
        if not KEY_HEX.match(c["key"]):
            errors.add("calls, key must be 64 hexadecimal digits, the SHA-256 digest of the canonical request", where)
            good = False
        for f in ("ts", "tokens_in", "tokens_out", "latency_s"):
            if c[f] < 0:
                errors.add("calls, %s is negative" % f, where)
                good = False
        if not good:
            continue
        k = c["key"].lower()
        sig = (c["endpoint"], c["model"], c["tokens_in"], c["tokens_out"], c["parse_ok"])
        if k not in first:
            first[k] = (sig, where)
        elif first[k][0] != sig:
            errors.add("calls, records of one key disagree on endpoint, model, tokens or parse_ok",
                       "%s against %s" % (where, first[k][1]))
            continue
        valid.append(c)
    errors.emit(err)
    if not calls and not info.get("source"):
        err("calls is empty, and only a run that reuses the decisions of another run, named in source_run_id, "
            "may have no calls")
    if valid and info.get("started") is not None and info.get("finished") is not None:
        out = [c for c in valid if c["ts"] < info["started"] - TIME_SLACK_S or c["ts"] > info["finished"] + TIME_SLACK_S]
        if out:
            warn("%d call(s) have a timestamp outside the run interval from started_at to finished_at" % len(out))
    models = {info.get("model_oracle"), info.get("model_proxy")} - {None}
    stray = sorted({c["model"] for c in valid if c["endpoint"] == "responses"} - models)
    if stray and models:
        warn("calls to the responses endpoint use %s, which is neither model_oracle nor model_proxy"
             % ", ".join(stray))
    return valid


def check_price_list(pl, name, err):
    """Checks a price list and returns it, or returns None when it is unusable."""
    if not isinstance(pl, dict):
        err("%s must be a JSON object with id, currency and models" % name)
        return None
    ok = True
    for f in ("id", "currency"):
        if not _type_ok(pl.get(f), "str"):
            err("%s.%s must be a non-empty string" % (name, f))
            ok = False
    models = pl.get("models")
    if not isinstance(models, dict) or not models:
        err("%s.models must be a non-empty object from model name to prices" % name)
        return None
    for m, p in models.items():
        for f in ("input_per_million", "output_per_million"):
            x = p.get(f) if isinstance(p, dict) else None
            if not _type_ok(x, "number") or x < 0:
                err("%s.models[%s].%s must be a number of at least 0" % (name, _show(m), f))
                ok = False
    return pl if ok else None


def validate_doc(doc, parts=None):
    """File-level checks of a parsed run file.

    parts holds (domain folder, data set folder, query folder, file name) from the path of the file, or
    None when the path is unknown. The function returns (problems, info). problems is a list of
    (level, message) pairs with level "error" or "warning", and info holds what later checks need.
    """
    out = []
    err = lambda m: out.append(("error", m))
    warn = lambda m: out.append(("warning", m))
    if not isinstance(doc, dict):
        err("the file holds %s, not a JSON object" % _jtype(doc))
        return out, {}
    if "format" in doc and doc["format"] != FORMAT:
        err('format is %s, and it must be "%s"' % (_show(doc["format"]), FORMAT))
    for k in TOP_FIELDS:
        if k not in doc:
            err("the key %s is missing" % k)
    for k in doc:
        if k not in TOP_FIELDS:
            warn("unknown key %s is ignored" % k)
    info = _check_run(doc["run"], parts, err, warn) if "run" in doc else _empty_info()
    kind, t = info.get("kind"), info.get("type")

    rows = None
    if "answer" in doc:
        rows = check_result_set(doc["answer"], "answer", ANSWER_ROLES.get(kind), err, warn)
        if rows is not None and not rows:
            warn("the answer is empty")
    info["rows"] = rows

    cand = doc.get("candidates")
    if cand is None:
        if t == "Q7" and "candidates" in doc:
            err("candidates is null, and a Q7-type run must give the pairs kept by blocking")
    elif kind is not None and kind != "join":
        warn("candidates is ignored for a query that is not a join")
    else:
        info["candidates"] = check_result_set(cand, "candidates", ("entity", "entity"), err, warn)

    oc = doc.get("oracle_check")
    if oc is not None:
        if not isinstance(oc, list):
            err("oracle_check must be null or an array of objects with left, right and answer")
        else:
            bad = [i for i, o in enumerate(oc) if not (isinstance(o, dict) and entity_string(o.get("left"))
                                                        and entity_string(o.get("right"))
                                                        and isinstance(o.get("answer"), bool))]
            if bad:
                err("oracle_check, %d record(s) lack a left and a right Q-id and a Boolean answer (first at "
                    "oracle_check[%d])" % (len(bad), bad[0]))
            elif kind is not None and kind != "join":
                warn("oracle_check is ignored for a query that is not a join")
            else:
                if len(oc) < MIN_ORACLE_CHECKS:
                    warn("oracle_check has %d records, and at least %d are expected" % (len(oc), MIN_ORACLE_CHECKS))
                if rows is not None and kind == "join":
                    out_pairs = pairs(rows)
                    stray = sum(1 for o in oc if (entity_string(o["left"]), entity_string(o["right"])) not in out_pairs)
                    if stray:
                        warn("oracle_check holds %d pair(s) that are not in the answer" % stray)

    calls = _check_calls(doc["calls"], info, err, warn) if "calls" in doc else []
    pl = check_price_list(doc["price_list"], "price_list", err) if "price_list" in doc else None
    if pl is not None:
        unpriced = sorted({c["model"] for c in calls} - set(pl["models"]))
        if unpriced:
            err("price_list.models has no price for %s" % ", ".join(unpriced))
    return out, info


# ---------------------------------------------------------------------------------------------------------
# Data packages, keys and submissions
# ---------------------------------------------------------------------------------------------------------

class DataSet(object):
    """One set of a data package, such as films/dev, read lazily."""

    def __init__(self, path):
        self.path = path
        self._sets, self._gt, self._years = None, {}, None

    def sets(self):
        if self._sets is None:
            self._sets = defaultdict(set)
            for row in read_csv(os.path.join(self.path, "sets.csv")):
                self._sets[row["set_id"].strip()].add(row["qid"].strip())
        return self._sets

    def gt(self, t):
        if t not in self._gt:
            self._gt[t] = read_csv(os.path.join(self.path, "gt", t.lower() + ".csv"))
        return self._gt[t]

    def years(self):
        if self._years is None:
            self._years = {}
            for row in read_csv(os.path.join(self.path, "entities.csv")):
                try:
                    self._years[row["qid"]] = int(float(row["first_year"]))
                except (TypeError, ValueError):
                    pass
        return self._years


class Run(object):
    """One run file, with its problems and, once scored, its metrics."""

    def __init__(self, path, root=None, rel=None):
        self.path, self.root, self.rel = path, root, rel or path
        self.doc, self.info, self.problems = None, {}, []
        self.metrics, self.key_path = None, None

    @property
    def run(self):
        return self.doc["run"]

    @property
    def usable(self):
        return self.doc is not None and not any(level == "error" for level, _ in self.problems)

    def error(self, message):
        self.problems.append(("error", message))

    def warning(self, message):
        self.problems.append(("warning", message))


class Submission(object):
    """The run files and answer keys of one repository."""

    def __init__(self, root):
        self.root = root
        self.runs = []
        self.problems = []          # Diagnostic tuples of the repository and of its key files
        self.group_id = None
        self.keys = {}              # relative key path -> (rows or None, list of (level, message))

    def by_id(self):
        out = {}
        for run in self.runs:
            rid = run.info.get("run_id")
            if rid is not None:
                out.setdefault(rid, run)
        return out


class Context(object):
    """What scoring needs beyond one repository, namely the data packages, published keys and official prices."""

    def __init__(self, data=None, keys_dir=None, prices=None, key_roots=None):
        self.data = dict(data or {})
        self.keys_dir = keys_dir
        self.prices = prices
        self.key_roots = dict(key_roots or {})      # group id -> repository root, for the keys of pool queries
        self._sets = {}
        self._keys = {}
        self.key_problems = defaultdict(list)       # key path -> [(level, message)]

    def dataset(self, domain, data_set):
        if domain not in self.data:
            return None
        k = (domain, data_set)
        if k not in self._sets:
            path = os.path.join(self.data[domain], data_set)
            self._sets[k] = DataSet(path) if os.path.isfile(os.path.join(path, "sets.csv")) else None
        return self._sets[k]

    def pool_key_path(self, domain, data_set, query_id):
        rel = os.path.join(domain, data_set, query_id, "key.json")
        places = []
        if self.keys_dir:
            places.append(os.path.join(self.keys_dir, rel))
        root = self.key_roots.get(query_id.split("-")[0])
        if root:
            places.append(os.path.join(root, "keys", rel))
        for p in places:
            if os.path.isfile(p):
                return p
        return None

    def key_rows(self, path, kind):
        """The solutions of a key.json, or None when it has errors, which go to key_problems."""
        k = (path, kind)
        if k not in self._keys:
            self._keys[k] = read_key_file(path, kind, self.key_problems[path])
        return self._keys[k]


def read_key_file(path, kind, problems):
    """Reads and checks the answer key of an own or pool query. Returns its solutions, or None on error."""
    err = lambda m: problems.append(("error", m))
    warn = lambda m: problems.append(("warning", m))
    try:
        doc = read_json(path)
    except (OSError, ValueError) as e:
        err(str(e))
        return None
    n = len(problems)
    rows = check_result_set(doc, "key", KEY_ROLES[kind], err, warn)
    if rows is None or any(level == "error" for level, _ in problems[n:]):
        return None
    if not rows:
        warn("the key has no solution")
    return rows


def find_repo_root(path):
    """The repository root of a run file at runs/<domain>/<data_set>/<query_id>/<run_id>.json, or None."""
    parts = os.path.abspath(path).split(os.sep)
    if len(parts) >= 6 and parts[-5] == "runs":
        return os.sep.join(parts[:-5]) or os.sep
    return None


def load_run(path, root=None):
    """Reads one run file and applies the file-level checks."""
    rel = os.path.relpath(path, root) if root else path
    run = Run(path, root, rel)
    parts = None
    if root is not None:
        p = rel.split(os.sep)
        if len(p) == 5 and p[0] == "runs":
            parts = tuple(p[1:])
    if parts is None:
        run.error("the file must lie at runs/<domain>/<data_set>/<query_id>/<run_id>.json in the repository")
    try:
        run.doc = read_json(path)
    except (OSError, ValueError) as e:
        run.error(str(e))
        return run
    problems, run.info = validate_doc(run.doc, parts)
    run.problems.extend(problems)
    if not isinstance(run.doc, dict):
        run.doc = None
    return run


def load_submission(root):
    """Reads every run file under root/runs and lists the key files under root/keys."""
    sub = Submission(root)
    base = os.path.join(root, "runs")
    if not os.path.isdir(base):
        sub.problems.append(Diagnostic("error", None, "the repository has no runs/ folder"))
        return sub
    for dirpath, dirnames, filenames in os.walk(base):
        dirnames[:] = sorted(d for d in dirnames if not d.startswith("."))
        for name in sorted(filenames):
            if name.endswith(".json") and not name.startswith("."):
                sub.runs.append(load_run(os.path.join(dirpath, name), root))
    ids = Counter(r.info.get("group_id") for r in sub.runs if r.info.get("group_id"))
    if ids:
        sub.group_id = ids.most_common(1)[0][0]
        if len(ids) > 1:
            sub.problems.append(Diagnostic("warning", None, "the run files carry the group ids %s; the repository "
                                           "counts as %s" % (", ".join(sorted(ids)), sub.group_id)))
    return sub


def check_submission(sub, ctx):
    """Submission-level checks, then the scoring of every usable run. Adds problems to runs and to sub."""
    runs = [r for r in sub.runs if r.doc is not None]
    by_id = defaultdict(list)
    for run in runs:
        if run.info.get("run_id"):
            by_id[run.info["run_id"]].append(run)
    for rid, same in by_id.items():
        if len(same) > 1:
            for run in same:
                run.error("run_id %s is also the run_id of %s" % (rid, ", ".join(o.rel for o in same if o is not run)))

    for run in runs:
        info, r = run.info, run.doc.get("run")
        if not isinstance(r, dict):
            continue
        ref = r.get("reference_run_id") if isinstance(r.get("reference_run_id"), str) else None
        if ref is not None and ref != info.get("run_id"):
            target = by_id.get(ref)
            if not target:
                run.error("reference_run_id %s names no run of the submission" % ref)
            else:
                ti = target[0].info
                if (ti.get("plan_id") != "ref" or ti.get("domain") != info.get("domain")
                        or ti.get("data_set") != info.get("data_set") or ti.get("query_id") != info.get("query_id")):
                    run.error("reference_run_id %s must name a run of the plan ref for the same domain, data_set "
                              "and query_id" % ref)
        src = r.get("source_run_id") if isinstance(r.get("source_run_id"), str) else None
        if src is not None and src != info.get("run_id"):
            target = by_id.get(src)
            if not target:
                run.error("source_run_id %s names no run of the submission" % src)
            elif (target[0].info.get("domain"), target[0].info.get("data_set")) != (info.get("domain"),
                                                                                    info.get("data_set")):
                run.error("source_run_id %s names a run on another domain or data set" % src)

    shipped = defaultdict(list)
    for run in runs:
        r = run.doc.get("run")
        if isinstance(r, dict) and r.get("shipped") is True and run.info.get("query_id"):
            shipped[(run.info["domain"], run.info["data_set"], run.info["query_id"])].append(run)
    for (dom, ds, qid), same in shipped.items():
        if len(same) > 1:
            for run in same:
                run.error("%d runs of %s on %s/%s are shipped, and at most one may be" % (len(same), qid, dom, ds))

    for run in runs:
        info = run.info
        if info.get("query_set") != "own" or not info.get("query_id") or not info.get("domain") \
                or not info.get("data_set"):
            continue
        rel = os.path.join("keys", info["domain"], info["data_set"], info["query_id"], "key.json")
        path = os.path.join(sub.root, rel)
        run.key_path = path
        if not os.path.isfile(path):
            run.error("the own query %s has no answer key at %s" % (info["query_id"], rel))
        elif ctx.key_rows(path, info["kind"]) is None:
            run.error("the answer key %s has errors" % rel)

    _check_key_folder(sub, ctx)
    _check_orders(runs)
    _check_mandatory(sub, runs)

    for run in runs:
        info, r = run.info, run.doc.get("run")
        if not isinstance(r, dict) or not run.usable:
            continue
        ref = r.get("reference_run_id")
        if ref is None and r.get("plan_id") != "ref" and info["kind"] in ("filter", "classify", "join"):
            if any(o.info.get("plan_id") == "ref" and o.info.get("query_id") == info["query_id"]
                   and o.info.get("domain") == info["domain"] and o.info.get("data_set") == info["data_set"]
                   for o in runs):
                run.warning("a ref run exists for this query and set, but reference_run_id is null, so the "
                            "approximation quality stays empty")

    for run in runs:
        if run.usable:
            run.metrics = run_metrics(run, sub, ctx)


def _check_key_folder(sub, ctx):
    """Checks every key.json under keys/, including keys that no run uses."""
    base = os.path.join(sub.root, "keys")
    if not os.path.isdir(base):
        return
    for dirpath, dirnames, filenames in os.walk(base):
        dirnames[:] = sorted(d for d in dirnames if not d.startswith("."))
        if "key.json" not in filenames:
            continue
        path = os.path.join(dirpath, "key.json")
        p = os.path.relpath(path, sub.root).split(os.sep)
        m = GROUP_QUERY_ID.match(p[3]) if len(p) == 5 else None
        if len(p) != 5 or p[1] not in DOMAINS or p[2] not in DATA_SETS or not m or m.group(2) == "Q5":
            sub.problems.append(Diagnostic("warning", os.path.relpath(path, sub.root),
                                           "this file is not at keys/<domain>/<data_set>/<group>-Q<n>/key.json "
                                           "and is ignored"))
            continue
        ctx.key_rows(path, KIND[m.group(2)])
        if sub.group_id and m.group(1) != sub.group_id:
            sub.problems.append(Diagnostic("warning", os.path.relpath(path, sub.root),
                                           "the key belongs to a query of %s, not of %s" % (m.group(1), sub.group_id)))


def _check_orders(runs):
    """Warns when the two orders of a Q3-type query return different answers."""
    groups = defaultdict(list)
    for run in runs:
        if run.info.get("type") == "Q3" and run.info.get("rows") is not None:
            groups[(run.info["domain"], run.info["data_set"], run.info["query_id"])].append(run)
    for same in groups.values():
        for s in (x for x in same if x.info.get("source")):
            for o in (x for x in same if not x.info.get("source") and x.info.get("plan_id") == s.info.get("plan_id")):
                a = {x[0] for x in s.info["rows"] if x[0]}
                b = {x[0] for x in o.info["rows"] if x[0]}
                if a != b:
                    s.warning("the answer (%d entities) differs from that of %s (%d entities), the other order of "
                              "this query with plan %s" % (len(a), o.info.get("run_id"), len(b), s.info.get("plan_id")))


def _check_mandatory(sub, runs):
    """Warns when a common mandatory query of the evaluation set lacks a run, a ref run or a clear choice."""
    domains = sorted({r.info["domain"] for r in runs if r.info.get("query_set") == "common" and r.info.get("domain")})
    if not domains:
        sub.problems.append(Diagnostic("warning", None, "the submission has no run of a common query"))
        return
    for dom in domains:
        for t in MANDATORY:
            same = [r for r in runs if r.info.get("query_set") == "common" and r.info.get("domain") == dom
                    and r.info.get("data_set") == "eval" and r.info.get("query_id") == t]
            if not same:
                sub.problems.append(Diagnostic("warning", None, "%s has no run on the evaluation set of %s" % (t, dom)))
                continue
            if t not in ("Q7", "Q8") and not any(r.info.get("plan_id") == "ref" for r in same):
                sub.problems.append(Diagnostic("warning", None,
                                               "%s has no run of the plan ref on the evaluation set of %s" % (t, dom)))
            usable = [r for r in same if r.usable]
            if len(usable) > 1 and select_run(usable, lambda r: r.run)[0] is None:
                sub.problems.append(Diagnostic("warning", None,
                                               "%s on the evaluation set of %s has %d usable runs and none is shipped, "
                                               "so the leaderboard cannot choose one" % (t, dom, len(usable))))


def select_run(candidates, fields=lambda x: x):
    """The run that represents a group for one query, with the reason for the choice.

    The shipped run comes first, then the only run, then the only run of the plan ref. Returns
    (None, reason) when no rule applies.
    """
    shipped = [c for c in candidates if fields(c).get("shipped") is True]
    if len(shipped) == 1:
        return shipped[0], "shipped"
    if len(shipped) > 1:
        return None, "%d runs shipped" % len(shipped)
    if len(candidates) == 1:
        return candidates[0], "only run"
    refs = [c for c in candidates if fields(c).get("plan_id") == "ref"]
    if len(refs) == 1:
        return refs[0], "ref run"
    return None, "%d runs, none shipped" % len(candidates) if candidates else "no run"


# ---------------------------------------------------------------------------------------------------------
# Metrics of one run
# ---------------------------------------------------------------------------------------------------------

def work_metrics(doc, official=None):
    """Work, cost, efficiency and health metrics from the call records of a valid run file.

    Returns (metrics, models missing from the official price list).
    """
    r, calls = doc["run"], doc["calls"]
    first, paid = OrderedDict(), set()
    for c in calls:
        k = c["key"].lower()
        first.setdefault(k, c)
        if not c["cache_hit"]:
            paid.add(k)
    responses = [c for c in calls if c["endpoint"] == "responses"]
    rkeys = [k for k, c in first.items() if c["endpoint"] == "responses"]
    ekeys = [k for k, c in first.items() if c["endpoint"] == "embeddings"]
    n = r["n_input_bindings"]

    def price(k, table):
        c = first[k]
        p = table[c["model"]]
        return (c["tokens_in"] * p["input_per_million"] + c["tokens_out"] * p["output_per_million"]) / 1e6

    table = doc["price_list"]["models"]
    missing, cost_official = [], None
    if official is not None:
        missing = sorted({c["model"] for c in first.values()} - set(official["models"]))
        if not missing:
            cost_official = float(sum(price(k, official["models"]) for k in first))
    latencies = sorted(first[k]["latency_s"] for k in rkeys)
    hits = sum(1 for c in responses if c["cache_hit"])
    m = dict(
        n_function_calls=len(responses), n_llm_calls=len(rkeys), n_embedding_requests=len(ekeys),
        cache_hit_rate=hits / len(responses) if responses else None,
        calls_per_input=len(responses) / n, llm_calls_per_input=len(rkeys) / n,
        tokens_in=sum(first[k]["tokens_in"] for k in rkeys), tokens_out=sum(first[k]["tokens_out"] for k in rkeys),
        embedding_tokens=sum(first[k]["tokens_in"] for k in ekeys),
        cost=float(sum(price(k, table) for k in first)),
        cost_paid=float(sum(price(k, table) for k in first if k in paid)),
        cost_official=cost_official,
        official_price_list_id=official["id"] if official is not None else None,
        currency=doc["price_list"]["currency"],
        model_seconds=float(sum(latencies)), latency_median_s=nearest_rank(latencies, 50),
        latency_p95_s=nearest_rank(latencies, 95),
        parse_failures=sum(1 for k in rkeys if not first[k]["parse_ok"]),
        oracle_fraction=(sum(1 for k in rkeys if first[k]["model"] == r["model_oracle"]) / n
                         if r["model_proxy"] else None),
    )
    return m, missing


def input_sets(ds, info):
    """The input entities of a query on a set, and the right side for a join (None for other types)."""
    t, S = info["type"], ds.sets()
    if info["kind"] == "join":
        side = "q6" if t == "Q6" else "q7"
        return S.get(side + "_left", set()), S.get(side + "_right", set())
    if info["query_set"] == "common" and t in ("Q3", "Q4"):
        return {row["qid"] for row in ds.gt(t)}, None
    return S.get("main", set()), None


def restriction(ds, r, info):
    """The entities, or left entities for a join, on which a run is scored; None means no restriction.

    A pool run is scored on the pool subset of the evaluation set, and a sampled run on its sample. Without a
    data set only the sample applies.
    """
    R = None
    if r["query_set"] == "pool" and ds is not None:
        S = ds.sets()
        if info["kind"] in ("filter", "classify", "extract", "count"):
            R = set(S.get("pool_main", set()))
        elif info["type"] == "Q7":
            R = set(S.get("pool_q7_left", set()))
    if r["sample"] is not None:
        sample = {entity_string(x) for x in r["sample"]["inputs"]}
        R = sample if R is None else R & sample
    return R


def restrict_rows(rows, inputs, R):
    """Drops the solutions whose entity, or left entity, is an input outside the restriction R.

    A solution whose entity is not an input at all stays, so that it counts as a false positive.
    """
    if R is None:
        return rows, 0
    kept = [x for x in rows if not (x[0] is not None and x[0] not in R and (inputs is None or x[0] in inputs))]
    return kept, len(rows) - len(kept)


def expected_inputs(ds, r, info):
    """(expected n_input_bindings, exact) for a common or pool run, or None when no expectation applies."""
    S, t = ds.sets(), info["type"]
    left, right = input_sets(ds, info)
    if r["sample"] is not None:
        n = len({entity_string(x) for x in r["sample"]["inputs"]})
        return (n * len(right) if right is not None else n), True
    if r["query_set"] == "common":
        return (len(left) * len(right) if right is not None else len(left)), True
    if r["query_set"] == "pool":
        if t == "Q6":
            return len(left) * len(right), True
        if t == "Q7":
            return len(S.get("pool_q7_left", ())) * len(right), True
        return len(S.get("pool_main", ())), t not in ("Q3", "Q4")
    return None


def _common_key(ds, t):
    """The answer key of a common query from gt/, as in tools/semops_eval.py."""
    rows, kind = ds.gt(t), KIND[t]
    if kind == "filter":
        return dict(inputs={r["qid"] for r in rows}, gold={r["qid"] for r in rows if r["path"] == "1"},
                    direct={r["qid"] for r in rows if r["direct"] == "1"})
    if kind == "classify":
        gold, names = {}, {}
        for r in rows:
            ids = r["labels"].split("|")
            gold[r["qid"]] = set(ids)
            for i, n in zip(ids, r["label_names"].split("|")):
                names[n.strip().lower()] = i
        return dict(gold=gold, names=names, labels=set().union(*gold.values()) if gold else set())
    if kind == "extract":
        return dict(gold={r["qid"]: set(r["values"].split("|")) for r in rows})
    if kind == "join":
        return dict(gold={(r["left"], r["right"]) for r in rows})
    return dict(gold={group(r["decade"]): float(r["positives"]) for r in rows})


def _file_key(rows, kind, inputs, right, note):
    """The answer key of an own or pool query from the solutions of its key.json, limited to the input set."""
    if kind == "filter":
        gold = {e for (e,) in rows}
        if inputs is not None:
            outside, gold = gold - inputs, gold & inputs
            if outside:
                note("lists %d entities outside the input set of the query, which the scorer ignores" % len(outside))
        return dict(inputs=inputs, gold=gold, direct=None)
    if kind == "classify":
        gold = {}
        for e, l in rows:
            gold.setdefault(e, set()).add(l)
        labels = set().union(*gold.values()) if gold else set()
        if inputs is not None:
            outside = set(gold) - inputs
            if outside:
                note("lists %d entities outside the input set of the query, which the scorer ignores" % len(outside))
                gold = {e: ls for e, ls in gold.items() if e in inputs}
        return dict(gold=gold, names={}, labels=labels)
    if kind == "join":
        gold = {(l, r) for l, r in rows}
        if inputs is not None:
            inside = {(l, r) for l, r in gold if l in inputs and r in right}
            if len(inside) != len(gold):
                note("lists %d pairs outside the two sides of the join, which the scorer ignores"
                     % (len(gold) - len(inside)))
            gold = inside
        return dict(gold=gold)
    entities = {(e, group(g)) for e, g in rows}
    if inputs is not None:
        inside = {(e, g) for e, g in entities if e in inputs}
        if len(inside) != len(entities):
            note("lists %d entities outside the input set of the query, which the scorer ignores"
                 % len({e for e, _ in entities - inside}))
        entities = inside
    return dict(entities=entities)


def _count_gold(key, ds, R, common):
    """True counts per group, recomputed on the restriction R when there is one."""
    if common:
        if R is None:
            return key["gold"]
        years = ds.years()
        gold = {}
        for row in ds.gt("Q1"):
            e = row["qid"]
            if e in R and e in years:
                g = group((years[e] // 10) * 10)
                gold[g] = gold.get(g, 0.0) + (row["path"] == "1")
        return gold
    gold = {}
    for e, g in key["entities"]:
        if R is None or e in R:
            gold[g] = gold.get(g, 0.0) + 1
    return gold


def run_metrics(run, sub, ctx):
    """Every metric of a usable run, with work and cost from its calls and effectiveness from its answer and key."""
    doc, r, info = run.doc, run.doc["run"], run.info
    m, missing = work_metrics(doc, ctx.prices)
    if missing:
        run.warning("the official price list has no price for %s, so cost_official stays empty" % ", ".join(missing))
    sample = r["sample"]
    m.update(n_answer_rows=len(doc["answer"]["results"]["bindings"]),
             sample_method=sample["method"] if sample else None,
             sample_size=len({entity_string(x) for x in sample["inputs"]}) if sample else None)
    ds = ctx.dataset(r["domain"], r["data_set"])
    if ds is None:
        what = "the input checks are" if r["query_set"] == "own" else "the input checks and the effectiveness are"
        run.warning("no data package for %s/%s, so %s skipped%s" % (
            r["domain"], r["data_set"], what, " (pass --data)" if r["domain"] not in ctx.data else ""))
        if r["query_set"] == "own":
            _effectiveness(run, sub, ctx, None, m)
        return m
    _input_checks(run, ds)
    _effectiveness(run, sub, ctx, ds, m)
    return m


def _input_checks(run, ds):
    r, info = run.run, run.info
    exp = expected_inputs(ds, r, info)
    n = r["n_input_bindings"]
    if exp is not None:
        want, exact = exp
        if (exact and n != want) or (not exact and n > want):
            run.warning("n_input_bindings is %d, and the %s size is %d" % (n, "expected" if exact else "largest", want))
    left, right = input_sets(ds, info)
    if r["sample"] is not None:
        outside = {entity_string(x) for x in r["sample"]["inputs"]} - left
        if outside:
            run.warning("%d sample input(s) lie outside the input set of the query" % len(outside))
    rows = info["rows"]
    if info["kind"] == "join":
        bad = {x for x in rows if x[0] not in left or x[1] not in right}
        cand = info.get("candidates") or []
        badc = {x for x in cand if x[0] not in left or x[1] not in right}
        if bad:
            run.warning("%d answer pair(s) lie outside the two sides of the join and count as false positives" % len(bad))
        if badc:
            run.warning("%d candidate pair(s) lie outside the two sides of the join" % len(badc))
    elif info["kind"] != "count":
        bad = {x[0] for x in rows} - left
        if bad:
            run.warning("%d answer entities lie outside the input set of the query%s" % (
                len(bad), " and count as false positives" if info["kind"] == "filter" else ""))


def _effectiveness(run, sub, ctx, ds, m):
    """Adds the effectiveness metrics of a usable run to m when its answer key is available."""
    doc, r, info = run.doc, run.run, run.info
    t, kind = info["type"], info["kind"]
    inputs, right = input_sets(ds, info) if ds is not None else (None, None)
    note_path = None
    if r["query_set"] == "common":
        key = _common_key(ds, t)
    else:
        if r["query_set"] == "own":
            path = run.key_path
        else:
            path = run.key_path = ctx.pool_key_path(r["domain"], r["data_set"], r["query_id"])
            if path is None:
                run.warning("no answer key of the pool query %s was found%s, so the effectiveness metrics stay "
                            "empty" % (r["query_id"], "" if ctx.keys_dir else " (pass --keys)"))
                return
        rows = ctx.key_rows(path, kind)
        if rows is None:
            if r["query_set"] == "pool":
                run.warning("the answer key %s has errors, so the effectiveness metrics stay empty" % path)
            return
        notes = []
        key = _file_key(rows, kind, inputs, right, notes.append)
        for n in notes:
            if ("warning", "the key " + n) not in ctx.key_problems[path]:
                ctx.key_problems[path].append(("warning", "the key " + n))

    R = restriction(ds, r, info)
    rows, dropped = restrict_rows(info["rows"], inputs, R)
    if dropped:
        run.warning("%d answer solution(s) lie outside the %s and are ignored"
                    % (dropped, "pool subset" if r["query_set"] == "pool" and r["sample"] is None else
                       "sample" if r["query_set"] != "pool" else "pool subset and the sample"))
    m["outside_restriction"] = dropped
    keep = (lambda e: True) if R is None else (lambda e: e in R)

    if kind == "filter":
        k = dict(inputs=(inputs & R if R is not None else inputs) if inputs is not None else None,
                 gold={e for e in key["gold"] if keep(e)},
                 direct={e for e in key["direct"] if keep(e)} if key["direct"] is not None else None)
        s = score_filter(k, rows)
        g = s["gt"]
        m.update(precision_gt=g["precision"], recall_gt=g["recall"], f1_gt=g["f1"], n_key=g["n_gold"],
                 recall_wilson_low=g["recall_wilson95"][0], recall_wilson_high=g["recall_wilson95"][1])
        if "gt_direct" in s:
            d = s["gt_direct"]
            m.update(precision_direct=d["precision"], recall_direct=d["recall"], f1_direct=d["f1"])
        if inputs is not None:
            m["outside_inputs"] = len({x[0] for x in rows if x[0]} - inputs)
    elif kind == "classify":
        gold = {e: ls for e, ls in key["gold"].items() if keep(e)}
        s = score_classify(dict(gold=gold, names=key["names"]), rows, labels=key["labels"])
        m.update(hit_rate=s["hit_rate"], accuracy=s["accuracy"], macro_f1=s["macro_f1"], outside_L=s["outside_L"],
                 missing=s["missing"], n_key=s["n_inputs"],
                 outside_inputs=len({x[0] for x in rows if x[0]} - inputs) if inputs is not None else s["outside_inputs"])
        if s["outside_L"]:
            run.warning("%d input(s) have a label outside the label set L" % s["outside_L"])
    elif kind == "extract":
        gold = {e: vs for e, vs in key["gold"].items() if keep(e)}
        s = score_extract(dict(gold=gold), rows)
        m.update(accuracy=s["accuracy"], unresolved_rate=s["unresolved_rate"], n_key=s["n_inputs"])
        if inputs is not None:
            m["outside_inputs"] = len({x[0] for x in rows if x[0]} - inputs)
    elif kind == "join":
        gold = {p for p in key["gold"] if keep(p[0])}
        cand = info.get("candidates")
        if cand is not None:
            cand, _ = restrict_rows(cand, inputs, R)
        s = score_join(dict(gold=gold), rows, cand=cand)
        g = s["gt"]
        m.update(precision_gt=g["precision"], recall_gt=g["recall"], f1_gt=g["f1"], n_key=g["n_gold"])
        if cand is not None:
            m.update(blocking_recall=s["blocking_recall"], n_candidates=s["n_candidates"],
                     outside_candidates=s["outside_candidates"])
        if inputs is not None:
            m["outside_inputs"] = sum(1 for x in pairs(rows) if x[0] not in inputs or x[1] not in right)
        oc = doc["oracle_check"]
        if oc:
            checks = [o for o in oc if R is None or entity_string(o["left"]) in R
                      or (inputs is not None and entity_string(o["left"]) not in inputs)]
            k = sum(1 for o in checks if o["answer"] is True)
            lo, hi = wilson(k, len(checks))
            m.update(oracle_checks=len(checks), oracle_agreement=k / len(checks) if checks else None,
                     oracle_agreement_low=lo, oracle_agreement_high=hi)
    else:
        gold = _count_gold(key, ds, R, r["query_set"] == "common")
        s = score_count(dict(gold=gold), info["rows"])
        m.update(rel_error=s["mare"], n_key=s["n_groups"],
                 zero_groups_predicted=s["zero_groups_predicted"] or None,
                 groups_outside_key=s["groups_outside_key"] or None)

    ref_id = r["reference_run_id"]
    if ref_id is not None and kind in ("filter", "classify", "join"):
        ref = sub.by_id().get(ref_id) if sub is not None else None
        if ref is None or not ref.usable:
            run.warning("the reference run %s is not usable, so the approximation quality stays empty" % ref_id)
            return
        R_ref = restriction(ds, ref.run, ref.info)
        R_both = R if R_ref is None else (R_ref if R is None else R & R_ref)
        a, _ = restrict_rows(info["rows"], inputs, R_both)
        b, _ = restrict_rows(ref.info["rows"], inputs, R_both)
        if kind == "filter":
            p = prf({x[0] for x in a if x[0]}, {x[0] for x in b if x[0]})
            m.update(precision_ref=p["precision"], recall_ref=p["recall"], f1_ref=p["f1"])
        elif kind == "join":
            p = prf(pairs(a), pairs(b))
            m.update(precision_ref=p["precision"], recall_ref=p["recall"], f1_ref=p["f1"])
        else:
            names = key["names"]
            gold = [e for e in key["gold"] if R_both is None or e in R_both]
            pred, _ = labels_of(a, names)
            rp, _ = labels_of(b, names)
            m["accuracy_ref"] = (sum(1 for e in gold if pred.get(e) is not None and pred.get(e) == rp.get(e))
                                 / len(gold) if gold else None)


def main_quality(kind):
    """The name of the primary quality column of a query type, and whether higher values are better."""
    return {"filter": ("f1_gt", True), "join": ("f1_gt", True), "classify": ("macro_f1", True),
            "extract": ("accuracy", True), "count": ("rel_error", False)}[kind]


def results_row(run):
    """The row of the results table of a scored run, as a dict of Python values."""
    r, m = run.run, run.metrics
    row = dict.fromkeys(RESULT_COLUMNS + EXTRA_COLUMNS)
    row.update(m)
    sample = r["sample"]
    row.update(group_id=r["group_id"], domain=r["domain"], data_set=r["data_set"], query_set=r["query_set"],
               query_id=r["query_id"], operator=OPERATOR[run.info["type"]], run_id=r["run_id"],
               plan_id=r["plan_id"],
               plan_params=json.dumps(r["plan_params"], sort_keys=True, separators=(",", ":"), ensure_ascii=False),
               model_oracle=r["model_oracle"], model_proxy=r["model_proxy"], n_input_bindings=r["n_input_bindings"],
               wallclock_s=r["wallclock_s"], price_list_id=run.doc["price_list"]["id"], spearman=None,
               shipped=r["shipped"], reference_run_id=r["reference_run_id"], source_run_id=r["source_run_id"],
               sample_method=sample["method"] if sample else None, pool_mode=r["pool_mode"], engine=r["engine"])
    return row


def format_cell(x):
    if x is None:
        return ""
    if isinstance(x, bool):
        return "true" if x else "false"
    if isinstance(x, int):
        return str(x)
    if isinstance(x, float):
        if x == int(x) and abs(x) < 1e15:
            return str(int(x))
        s = ("%.10f" % x).rstrip("0").rstrip(".")
        return s if s not in ("", "-0") else "0"
    if isinstance(x, (dict, list)):
        return json.dumps(x, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return str(x)


def write_csv(rows, path, columns):
    """Writes rows, dicts of Python values, as CSV with the given columns."""
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(columns)
        for row in rows:
            w.writerow([format_cell(row.get(c)) for c in columns])


def write_results_csv(rows, path):
    """Writes the results table, the 36 columns of the brief followed by the extra columns."""
    write_csv(rows, path, RESULT_COLUMNS + EXTRA_COLUMNS)


# ---------------------------------------------------------------------------------------------------------
# Helpers for students
# ---------------------------------------------------------------------------------------------------------

def _log_time(x, where):
    if isinstance(x, bool):
        raise ValueError("%s, ts must be a number or an ISO 8601 UTC time" % where)
    if isinstance(x, (int, float)):
        return float(x)
    if isinstance(x, str):
        t = parse_utc(x.strip())
        if t is not None:
            return t
        try:
            return float(x)
        except ValueError:
            pass
    raise ValueError("%s, ts must be a number or an ISO 8601 UTC time" % where)


def _log_bool(x, name, where):
    if isinstance(x, bool):
        return x
    if x in (0, 1) and not isinstance(x, float):
        return bool(x)
    raise ValueError("%s, %s must be true or false" % (where, name))


def calls_from_log(log_path, run_id):
    """The call records of one run, read from the gateway log.

    The log has one JSON object per line. Each line of the run carries ts (Unix seconds or an ISO 8601 UTC
    time), run_id (the IRI of the run node or its local name), endpoint or api, key, model, cache_hit,
    parse_ok, tokens_in, tokens_out and latency_s. Other fields are ignored. The function keeps the lines
    whose run_id has the local name of run_id, in the order of the log. It maps an endpoint that ends in
    responses or chat/completions to "responses" and one that ends in embeddings to "embeddings". It raises
    ValueError when a line of the run lacks a field.
    """
    want = local_name(run_id)
    out = []
    with open(log_path, encoding="utf-8") as f:
        for n, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            where = "%s, line %d" % (log_path, n)
            try:
                rec = json.loads(line)
            except ValueError:
                raise ValueError("%s is not a JSON object" % where)
            if not isinstance(rec, dict) or not isinstance(rec.get("run_id"), str) \
                    or local_name(rec["run_id"]) != want:
                continue
            ep = rec.get("endpoint", rec.get("api"))
            for f_ in ("key", "model", "cache_hit", "parse_ok", "tokens_in", "tokens_out", "latency_s", "ts"):
                if f_ not in rec:
                    raise ValueError("%s has no %s" % (where, f_))
            if not isinstance(ep, str):
                raise ValueError("%s has no endpoint or api" % where)
            ep = ep.strip().lower().rstrip("/")
            if ep.endswith("embeddings"):
                ep = "embeddings"
            elif ep.endswith("responses") or ep.endswith("completions"):
                ep = "responses"
            try:
                tokens_in, tokens_out, latency = int(rec["tokens_in"]), int(rec["tokens_out"]), float(rec["latency_s"])
            except (TypeError, ValueError):
                raise ValueError("%s, tokens_in, tokens_out and latency_s must be numbers" % where)
            out.append(OrderedDict([
                ("ts", _log_time(rec["ts"], where)), ("endpoint", ep), ("key", str(rec["key"]).lower()),
                ("model", rec["model"]), ("cache_hit", _log_bool(rec["cache_hit"], "cache_hit", where)),
                ("parse_ok", _log_bool(rec["parse_ok"], "parse_ok", where)), ("tokens_in", tokens_in),
                ("tokens_out", tokens_out), ("latency_s", latency)]))
    return out


def run_path(run):
    """The path of a run file relative to the repository root."""
    return os.path.join("runs", run["domain"], run["data_set"], run["query_id"], run["run_id"] + ".json")


def dumps_run(doc):
    """A run file as JSON text, with one solution and one call record per line."""
    def one(x):
        return json.dumps(x, ensure_ascii=False, allow_nan=False)

    def result_set(rs):
        if not isinstance(rs, dict) or set(rs) != {"head", "results"} or not isinstance(rs["results"], dict) \
                or not isinstance(rs["results"].get("bindings"), list):
            return one(rs)
        rest = OrderedDict((k, v) for k, v in rs["results"].items() if k != "bindings")
        lines = ['{"head": %s, "results": {' % one(rs.get("head"))]
        for k, v in rest.items():
            lines[-1] += "%s: %s, " % (one(k), one(v))
        b = rs["results"]["bindings"]
        lines[-1] += '"bindings": [' + ("" if b else "]}}")
        for i, x in enumerate(b):
            lines.append("    " + one(x) + ("," if i < len(b) - 1 else "]}}"))
        return "\n".join(lines)

    def records(xs):
        if not isinstance(xs, list) or not xs:
            return one(xs)
        return "[\n" + ",\n".join("    " + one(x) for x in xs) + "]"

    parts = []
    for k, v in doc.items():
        if k in ("answer", "candidates") and v is not None:
            text = result_set(v)
        elif k in ("calls", "oracle_check"):
            text = records(v)
        elif k in ("run", "price_list"):
            text = json.dumps(v, ensure_ascii=False, allow_nan=False, indent=2).replace("\n", "\n  ")
        else:
            text = one(v)
        parts.append("  %s: %s" % (one(k), text))
    return "{\n" + ",\n".join(parts) + "\n}\n"


def write_run_file(repo_root, doc):
    """Validates a run file and writes it to runs/<domain>/<data_set>/<query_id>/<run_id>.json.

    doc is the run file as a dict. The function raises RunFileError, and writes nothing, when the file has
    errors. It prints the warnings to the standard error and returns the path of the written file. The checks
    are those of one file; the checker also runs the checks that need the whole submission and the data.
    """
    r = doc.get("run") if isinstance(doc, dict) else None
    fields = ("domain", "data_set", "query_id", "run_id")
    if not isinstance(r, dict) or not all(_type_ok(r.get(f), "str") for f in fields):
        raise RunFileError(["run.domain, run.data_set, run.query_id and run.run_id are needed to place the file"])
    if not all(RUN_ID.match(r[f]) for f in fields):
        raise RunFileError(["run.domain, run.data_set, run.query_id and run.run_id must be names without "
                            "slashes or spaces"])
    rel = run_path(r)
    try:
        text = dumps_run(doc)
        parsed = json.loads(text, object_pairs_hook=OrderedDict)
    except (TypeError, ValueError) as e:
        raise RunFileError(["the run file cannot be written as JSON, %s" % e])
    problems, _ = validate_doc(parsed, tuple(rel.split(os.sep)[1:]))
    errors = [m for level, m in problems if level == "error"]
    if errors:
        raise RunFileError(errors)
    path = os.path.join(repo_root, rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    for level, m in problems:
        sys.stderr.write("semops_check warning, %s, %s\n" % (rel, m))
    return path


# ---------------------------------------------------------------------------------------------------------
# Command line
# ---------------------------------------------------------------------------------------------------------

def parse_data_args(items):
    """A dict from domain to package path, read from arguments such as films=data/films."""
    data = {}
    for item in items or []:
        dom, sep, path = item.partition("=")
        dom, path = dom.strip(), path.strip()
        if not sep or dom not in DOMAINS or not path:
            raise ValueError("--data takes domain=package pairs, such as films=data/films, not %r" % item)
        if not any(os.path.isfile(os.path.join(path, ds, "sets.csv")) for ds in DATA_SETS):
            raise ValueError("%s is not a data package, since neither dev/sets.csv nor eval/sets.csv exists" % path)
        data[dom] = path
    return data


def read_price_file(path):
    """An official price list, checked. Raises ValueError when it is unusable."""
    errors = []
    pl = check_price_list(read_json(path), "the price list", errors.append)
    if pl is None or errors:
        raise ValueError("%s, %s" % (path, "; ".join(errors)))
    return pl


def fmt_value(x, digits=3):
    if x is None:
        return "-"
    if isinstance(x, float):
        return "%.*f" % (digits, x)
    return str(x)


def summary_line(run):
    """One line with the identity, the answer size, the main quality metric, the work and the cost of a run."""
    r, m = run.run, run.metrics
    col, _ = main_quality(run.info["kind"])
    label = {"f1_gt": "F1", "macro_f1": "macro-F1", "accuracy": "accuracy", "rel_error": "MARE"}[col]
    quality = "%s %s" % (label, fmt_value(m.get(col))) if m.get(col) is not None else "%s -" % label
    return ("%-8s %s/%-5s %-10s %-28s rows %5d  %-15s calls %6d  llm %6d  hits %s  tokens %d/%d  cost %s %s  "
            "wall %s s" % (r["query_id"], r["domain"], r["data_set"], r["plan_id"][:10], r["run_id"][:28],
                           m["n_answer_rows"], quality, m["n_function_calls"], m["n_llm_calls"],
                           fmt_value(m["cache_hit_rate"], 2), m["tokens_in"], m["tokens_out"], fmt_value(m["cost"], 4),
                           m["currency"], fmt_value(float(r["wallclock_s"]), 1)))


def check_paths(paths, ctx):
    """Loads and checks the repositories and run files named on the command line.

    Returns a list of (submission, focus) pairs, where focus is None for a whole repository or the set of
    run file paths named explicitly.
    """
    roots = OrderedDict()
    for p in paths:
        if os.path.isdir(p):
            roots.setdefault(os.path.abspath(p), None)
        else:
            root = find_repo_root(p)
            key = root if root is not None else ("file", os.path.abspath(p))
            focus = roots.setdefault(key, set())
            if focus is not None:
                focus.add(os.path.abspath(p))
    subs = []
    for root, focus in roots.items():
        if isinstance(root, tuple):
            sub = Submission(None)
            run = load_run(root[1])
            sub.runs.append(run)
            if run.usable:
                run.metrics = run_metrics(run, sub, ctx)
            subs.append((sub, {root[1]}))
            continue
        sub = load_submission(root)
        subs.append((sub, focus))
    for sub, _ in subs:
        if sub.root is not None and sub.group_id:
            ctx.key_roots.setdefault(sub.group_id, sub.root)
    for sub, _ in subs:
        if sub.root is not None:
            check_submission(sub, ctx)
    return subs


def print_report(subs, ctx, out=None):
    """Prints the problems of every file and the summary lines. Returns the number of errors."""
    out = out or sys.stdout
    n_err = n_warn = 0
    lines = []
    for sub, focus in subs:
        chosen = [r for r in sub.runs if focus is None or os.path.abspath(r.path) in focus]
        blocks = []
        if focus is None:
            grouped = OrderedDict()
            for d in sub.problems:
                grouped.setdefault(d.path or "(repository)", []).append((d.level, d.message))
            blocks.extend(grouped.items())
        keys = sorted({r.key_path for r in chosen if r.key_path}) if focus is not None else sorted(ctx.key_problems)
        for kp in keys:
            inside = sub.root is not None and os.path.abspath(kp).startswith(os.path.abspath(sub.root) + os.sep)
            if (inside or focus is not None) and ctx.key_problems.get(kp):
                blocks.append((os.path.relpath(kp, sub.root) if inside else kp, ctx.key_problems[kp]))
        for r in chosen:
            if r.problems:
                blocks.append((r.rel, r.problems))
        head = sub.root or "run files"
        lines.append("== %s" % head)
        for where, problems in blocks:
            lines.append(where)
            for level, message in problems:
                lines.append("  %s: %s" % (level, message))
                n_err += level == "error"
                n_warn += level == "warning"
        scored = [r for r in chosen if r.metrics is not None]
        if scored:
            lines.append("")
            for r in sorted(scored, key=lambda x: (x.run["domain"], x.run["data_set"], x.run["query_set"],
                                                   x.run["query_id"], x.run["run_id"])):
                lines.append(summary_line(r))
        bad = sum(1 for r in chosen if not r.usable)
        lines.append("%d run file(s), %d usable, %d with errors" % (len(chosen), len(chosen) - bad, bad))
        lines.append("")
    published = [kp for kp in sorted(ctx.key_problems) if ctx.key_problems[kp] and ctx.keys_dir
                 and os.path.abspath(kp).startswith(os.path.abspath(ctx.keys_dir) + os.sep)
                 and all(focus is None for _, focus in subs)]
    if published:
        lines.append("== published keys")
        for kp in published:
            lines.append(kp)
            for level, message in ctx.key_problems[kp]:
                lines.append("  %s: %s" % (level, message))
                n_err += level == "error"
                n_warn += level == "warning"
        lines.append("")
    lines.append("%d error(s), %d warning(s)" % (n_err, n_warn))
    out.write("\n".join(lines) + "\n")
    return n_err


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="Check the run files of a repository, compute the metrics of every run and write the results "
                    "table.")
    ap.add_argument("paths", nargs="+", help="a repository root, or run files")
    ap.add_argument("--data", nargs="+", metavar="DOMAIN=PACKAGE", help="data packages, such as films=data/films")
    ap.add_argument("--keys", help="a directory of published answer keys, <domain>/<data_set>/<query_id>/key.json")
    ap.add_argument("--prices", help="an official price list, for the column cost_official")
    ap.add_argument("--results", help="write the results table to this CSV file")
    a = ap.parse_args(argv)
    try:
        data = parse_data_args(a.data)
        prices = read_price_file(a.prices) if a.prices else None
    except (OSError, ValueError) as e:
        sys.stderr.write("error: %s\n" % e)
        return 2
    for p in a.paths:
        if not os.path.exists(p):
            sys.stderr.write("error: %s does not exist\n" % p)
            return 2
    ctx = Context(data, a.keys, prices)
    subs = check_paths(a.paths, ctx)
    n_err = print_report(subs, ctx)
    if a.results:
        rows = [results_row(r) for sub, focus in subs for r in sub.runs
                if r.metrics is not None and (focus is None or os.path.abspath(r.path) in focus)]
        write_results_csv(rows, a.results)
        print("wrote %d row(s) to %s" % (len(rows), a.results))
    return 1 if n_err else 0


if __name__ == "__main__":
    sys.exit(main())
