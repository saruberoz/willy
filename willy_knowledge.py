"""Offline fix guides for Willy.

Small Markdown guides in willy/knowledge/ hold proven checks and fixes for
common Linux problems. Before Willy answers, the guides that best match the
problem (or an error in a command's output) are attached to that message, so
the brain follows tested steps instead of guessing.

Search is a small BM25 keyword index: standard library only, instant, offline.
Guides are attached to the message (not the system prompt) so the engine's
conversation cache stays valid and replies stay fast.

Created by Wilson Sumanang.
"""

import math
import os
import re

STOPWORDS = set("""
a an and are as at be been but by can could do does did doing don't for from had has have having
he her here hers him his how i i'm if in into is it it's its just me my myself no not now of off
on once only or our out over please so some such than that the their them then there these they
this to too under until up very was we were what when where which while who why will with would
you your yours yourself help fix fixed problem problems issue issues working work works doesn't
didn't won't can't isn't wont cant dont linux ubuntu system anymore suddenly
still keep keeps got get getting since after today yesterday also again any all one
don doesn didn won isn aren wasn weren haven hasn couldn shouldn wouldn know knows idea why
what need needs want wants think seem seems look looks like really just thing things way tell
""".split())
TOKEN_RE = re.compile(r"[a-z0-9][a-z0-9_.+:/-]*[a-z0-9]|[a-z0-9]")
FIELD_WEIGHT = {"title": 3, "keywords": 3, "body": 1}


def tokenize(text):
    out = []
    for tok in TOKEN_RE.findall(text.lower()):
        for part in re.split(r"[/:.]", tok) if "/" in tok or ":" in tok else [tok]:
            part = part.strip("-_.+")
            if not part or part in STOPWORDS or len(part) < 2 or part.isdigit():
                continue
            if len(part) > 3 and part.endswith("s") and not part.endswith(("ss", "us", "is")):
                part = part[:-1]
            out.append(part)
    return out


class Guide(object):
    def __init__(self, path, text):
        self.path = path
        self.id = os.path.splitext(os.path.basename(path))[0]
        lines = text.strip().splitlines()
        self.title = lines[0].lstrip("# ").strip() if lines else self.id
        self.keywords = ""
        body = []
        for line in lines[1:]:
            if line.lower().startswith("keywords:") and not self.keywords:
                self.keywords = line.split(":", 1)[1]
            else:
                body.append(line)
        self.body = "\n".join(body).strip()
        self.terms = {}
        # Section headings like "## Check (read-only)" appear in every guide; leave them out
        # of the index so words like "read-only" keep their meaning for search.
        indexed_body = re.sub(r"(?m)^#+ .*$", "", self.body)
        for field, text_ in (("title", self.title), ("keywords", self.keywords), ("body", indexed_body)):
            for t in tokenize(text_):
                self.terms[t] = self.terms.get(t, 0) + FIELD_WEIGHT[field]
        self.length = sum(self.terms.values())


class Knowledge(object):
    def __init__(self, directory, max_chars=2600):
        self.guides = []
        self.max_chars = max_chars
        if directory and os.path.isdir(directory):
            for name in sorted(os.listdir(directory)):
                if name.endswith(".md"):
                    path = os.path.join(directory, name)
                    try:
                        with open(path, encoding="utf-8") as fh:
                            self.guides.append(Guide(path, fh.read()))
                    except OSError:
                        continue
        n = len(self.guides)
        self.avg_len = (sum(g.length for g in self.guides) / n) if n else 1.0
        df = {}
        for g in self.guides:
            for t in g.terms:
                df[t] = df.get(t, 0) + 1
        self.idf = {t: math.log(1 + (n - d + 0.5) / (d + 0.5)) for t, d in df.items()}

    def __len__(self):
        return len(self.guides)

    def search(self, text, k=2, min_score=3.5):
        """Return up to k (score, guide) pairs, best first, above min_score."""
        terms = set(tokenize(text))
        k1, b = 1.2, 0.75
        scored = []
        for g in self.guides:
            s = 0.0
            for t in terms:
                tf = g.terms.get(t)
                if tf:
                    s += self.idf[t] * tf * (k1 + 1) / (tf + k1 * (1 - b + b * g.length / self.avg_len))
            if s >= min_score:
                scored.append((s, g))
        scored.sort(key=lambda x: -x[0])
        if len(scored) > 1 and scored[1][0] < scored[0][0] * 0.7:
            scored = scored[:1]  # a clear winner: don't add a weak second guide
        return scored[:k]

    def augment(self, text, seen, k=2, min_score=3.5):
        """Return (text to append to a message, guide titles) for matching guides not
        already given in this conversation. Updates `seen`."""
        picks = [(s, g) for s, g in self.search(text, k=k, min_score=min_score) if g.id not in seen]
        if not picks:
            return "", []
        parts = ["\n\n[Willy fix guides: proven steps for this kind of problem. Follow them when "
                 "they fit; say so if they don't.]"]
        for _, g in picks:
            seen.add(g.id)
            body = g.body
            if len(body) > self.max_chars:
                body = body[:self.max_chars].rsplit("\n", 1)[0] + "\n..."
            parts.append("--- Guide: %s ---\n%s" % (g.title, body))
        return "\n".join(parts), [g.title for _, g in picks]
