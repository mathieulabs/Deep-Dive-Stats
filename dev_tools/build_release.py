# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
"""Build dist/Deep_Dive_Stats.ankiaddon and audit it first.

    python dev_tools/build_release.py            audit, then build
    python dev_tools/build_release.py --check    audit only

The package holds only what the add-on needs to run: no user data, git history,
editor settings or dev tools.

FAIL stops the build (personal terms, absolute user paths, e-mails, secrets,
user data in the package, French comments, em or en dashes in comments, files
that do not compile). WARN is for review only (print calls, TODOs, symbols,
wording).

Extra words to reject (your name, handles) go one per line in
dev_tools/.personal_terms, or comma-separated in BUILD_PERSONAL_TERMS. Terms
match whole words only, outside URLs. The system user name is checked too when
it has 4+ characters and is not a generic account name.
"""

import ast
import getpass
import io
import os
import re
import sys
import tokenize
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIST = os.path.join(ROOT, "dist")

PACKAGE_NAME = "Deep Dive Stats"
PACKAGE_ID = "deep_dive_stats"
# Anki 23.10 is the first version with FSRS data on cards.
MIN_POINT_VERSION = 231000
OUTPUT_NAME = "Deep_Dive_Stats.ankiaddon"

TERMS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".personal_terms")


def load_personal_terms():
    terms = [t for t in os.environ.get("BUILD_PERSONAL_TERMS", "").split(",")]
    if os.path.exists(TERMS_FILE):
        with open(TERMS_FILE, encoding="utf-8") as handle:
            terms += handle.read().splitlines()
    return [t.strip().lower() for t in terms if t.strip() and not t.strip().startswith("#")]

# What goes into the package: these top-level entries only.
INCLUDE_TOP = ["__init__.py", "LICENSE", "src"]

EXCLUDE_DIRS = {"__pycache__", ".git", ".claude", "cache", "user_files", "dist", "dev_tools"}
EXCLUDE_EXT = {".pyc", ".pyo", ".log", ".pkl", ".bundle", ".tar", ".tgz", ".gz", ".zip", ".7z",
               ".md", ".flag"}
EXCLUDE_NAMES = {"meta.json", ".DS_Store", ".gitignore", "debug.log"}

# Anything matching these inside the package is a hard failure.
FORBIDDEN_PARTS = {"user_files", "cache", ".git", ".claude", "__pycache__", "dev_tools"}
FORBIDDEN_NAMES = {"meta.json", "debug.log"}
FORBIDDEN_EXT = {".pkl", ".log", ".bundle", ".pyc", ".tar", ".tgz", ".gz", ".zip", ".7z", ".flag"}

TEXT_EXT = {".py", ".json", ".txt", ".qss", ".css", ".html", ".js", ".svg", ".md", ".cfg", ".ini"}

FRENCH_WORDS = {
    "le", "la", "les", "des", "une", "un", "du", "pour", "avec", "dans", "est", "sont",
    "pas", "que", "qui", "sur", "mais", "donc", "ou", "et", "au", "aux", "ce", "cette",
    "ces", "son", "sa", "ses", "il", "elle", "nous", "vous", "sans", "sous", "afin",
    "quand", "comme", "plus", "moins", "tout", "tous", "fait", "faire", "ici", "voir",
}
FRENCH_ACCENTS = re.compile(r"[àâçéèêëîïôûùüÿœÀÂÇÉÈÊËÎÏÔÛÙÜŸŒ]")

AI_PHRASES = re.compile(
    r"\b(robust|seamless(ly)?|leverag(e|es|ing)|comprehensive|elegant(ly)?|delve|"
    r"furthermore|moreover|in order to|ensure that|it is worth noting|"
    r"note that|let's|we need to|we can|we should|this ensures|carefully|"
    r"gracefully|under the hood|crucial|critical(ly)?|paramount|"
    r"best practice|production[- ]ready|state[- ]of[- ]the[- ]art)\b",
    re.IGNORECASE,
)
SYMBOLS = re.compile(r"[\u2190-\u21ff\u2600-\u27bf\u2705\u274c\U0001F300-\U0001FAFF]")
DASHES = re.compile(r"[\u2013\u2014]")
TODO_RE = re.compile(r"\b(TODO|FIXME|HACK|XXX)\b")
ABS_PATH_RE = re.compile(r"(?<![\w.])([A-Za-z]:\\\\?(Users|Documents|Projects)|/Users/\w+|/home/\w+|C:/Users)", re.IGNORECASE)
EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
URL_RE = re.compile(r"https?://\S+")
# System user names too generic to flag as personal.
GENERIC_USER_NAMES = {"root", "admin", "administrator", "user", "users", "guest", "dev", "test",
                      "default", "owner", "anki", "home", "build", "runner", "ubuntu"}
SECRET_RE = re.compile(
    r"(api[_-]?key|secret|token|passwd|password)\s*[:=]\s*['\"][A-Za-z0-9_\-]{12,}['\"]",
    re.IGNORECASE,
)


def collect_files():
    files = []
    for top in INCLUDE_TOP:
        path = os.path.join(ROOT, top)
        if os.path.isfile(path):
            files.append(top)
            continue
        for base, dirs, names in os.walk(path):
            dirs[:] = sorted(d for d in dirs if d not in EXCLUDE_DIRS)
            for name in sorted(names):
                ext = os.path.splitext(name)[1].lower()
                if name in EXCLUDE_NAMES or ext in EXCLUDE_EXT:
                    continue
                rel = os.path.relpath(os.path.join(base, name), ROOT).replace(os.sep, "/")
                files.append(rel)
    return files


def manifest_bytes():
    return ('{\n    "name": "%s",\n    "package": "%s",\n    "min_point_version": %d\n}\n' % (PACKAGE_NAME, PACKAGE_ID, MIN_POINT_VERSION)).encode("utf-8")


def read_text(rel):
    with open(os.path.join(ROOT, rel), "rb") as handle:
        raw = handle.read()
    return raw.decode("utf-8-sig", errors="replace")


def python_texts(source):
    """Yield (line, kind, text) for every comment and docstring in a Python file."""
    try:
        for tok in tokenize.generate_tokens(io.StringIO(source).readline):
            if tok.type == tokenize.COMMENT:
                yield tok.start[0], "comment", tok.string.lstrip("#").strip()
    except (tokenize.TokenError, IndentationError):
        pass
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            doc = ast.get_docstring(node, clean=False)
            if doc and node.body:
                yield node.body[0].lineno, "docstring", doc


def looks_french(text):
    if FRENCH_ACCENTS.search(text):
        return True
    words = re.findall(r"[a-zA-Z']+", text.lower())
    hits = sum(1 for w in words if w in FRENCH_WORDS)
    return len(words) >= 3 and hits >= 3 and hits / len(words) > 0.3


def audit(files):
    fails, warns = [], []

    def fail(rel, line, msg):
        fails.append(f"{rel}:{line}: {msg}")

    def warn(rel, line, msg):
        warns.append(f"{rel}:{line}: {msg}")

    terms = set(load_personal_terms())
    try:
        user = getpass.getuser().lower()
        if len(user) >= 4 and user not in GENERIC_USER_NAMES:
            terms.add(user)
    except Exception:
        pass
    terms.discard("")
    term_res = [(t, re.compile(r"(?<!\w)" + re.escape(t) + r"(?!\w)")) for t in sorted(terms)]

    for rel in files:
        parts = rel.split("/")
        name = parts[-1]
        ext = os.path.splitext(name)[1].lower()
        if set(parts[:-1]) & FORBIDDEN_PARTS or name in FORBIDDEN_NAMES or ext in FORBIDDEN_EXT:
            fail(rel, 0, "file must not be in the package")
            continue
        if ext not in TEXT_EXT:
            continue

        text = read_text(rel)
        lines = text.splitlines()

        for i, line in enumerate(lines, 1):
            low = URL_RE.sub(" ", line.lower())
            for term, term_re in term_res:
                if term_re.search(low):
                    fail(rel, i, f"personal term '{term}': {line.strip()[:80]}")
            if ABS_PATH_RE.search(line):
                fail(rel, i, f"absolute user path: {line.strip()[:80]}")
            if EMAIL_RE.search(line) and "@" in line and not line.strip().startswith(("#", "@")):
                match = EMAIL_RE.search(line).group(0)
                if not match.startswith("@") and "." in match.split("@")[-1]:
                    fail(rel, i, f"e-mail address: {match}")
            if SECRET_RE.search(line):
                fail(rel, i, "possible secret or token")

        if ext != ".py":
            continue

        try:
            compile(text, rel, "exec")
        except SyntaxError as exc:
            fail(rel, exc.lineno or 0, f"does not compile: {exc.msg}")
            continue

        for line_no, kind, body in python_texts(text):
            if looks_french(body):
                fail(rel, line_no, f"French {kind}: {body.strip().splitlines()[0][:70]}")
            if DASHES.search(body):
                fail(rel, line_no, f"em/en dash in {kind}")
            if AI_PHRASES.search(body):
                m = AI_PHRASES.search(body)
                warn(rel, line_no, f"wording to review in {kind}: '{m.group(0)}'")
            if SYMBOLS.search(body):
                warn(rel, line_no, f"symbol or emoji in {kind}")
            if TODO_RE.search(body):
                warn(rel, line_no, f"{TODO_RE.search(body).group(1)} left in {kind}")

        try:
            tree = ast.parse(text)
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "print":
                warn(rel, node.lineno, "print() call")
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                if DASHES.search(node.value):
                    warn(rel, node.lineno, "em/en dash in a string")

    return fails, warns


def build(files):
    os.makedirs(DIST, exist_ok=True)
    out = os.path.join(DIST, OUTPUT_NAME)
    if os.path.exists(out):
        os.remove(out)
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("manifest.json", manifest_bytes())
        for rel in files:
            zf.write(os.path.join(ROOT, rel), rel)
    return out


def verify_package(path):
    problems = []
    with zipfile.ZipFile(path) as zf:
        names = zf.namelist()
        if "manifest.json" not in names or "__init__.py" not in names:
            problems.append("manifest.json or __init__.py missing at the package root")
        for name in names:
            parts = name.split("/")
            if set(parts[:-1]) & FORBIDDEN_PARTS or parts[-1] in FORBIDDEN_NAMES:
                problems.append(f"forbidden entry in package: {name}")
            if os.path.splitext(name)[1].lower() in FORBIDDEN_EXT:
                problems.append(f"forbidden entry in package: {name}")
    return names, problems


def main():
    check_only = "--check" in sys.argv
    files = collect_files()
    fails, warns = audit(files)

    print(f"{len(files)} files checked.")
    for w in warns[:200]:
        print("WARN ", w)
    if len(warns) > 200:
        print(f"WARN  ... and {len(warns) - 200} more")
    for f in fails:
        print("FAIL ", f)
    print(f"\n{len(fails)} failure(s), {len(warns)} warning(s).")

    if fails:
        print("Build refused. Fix the failures above and run again.")
        return 1
    if check_only:
        return 0

    out = build(files)
    names, problems = verify_package(out)
    if problems:
        for p in problems:
            print("FAIL ", p)
        os.remove(out)
        return 1
    size = os.path.getsize(out) / 1024
    print(f"\nPackage ready: {out} ({size:.0f} KB, {len(names)} files)")
    print("Install it in Anki with Tools > Add-ons > Install from file.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
