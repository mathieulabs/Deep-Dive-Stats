# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
"""Check the interface translations (src/i18n/<language>.json) against the code.

    python dev_tools/check_translations.py              check every language
    python dev_tools/check_translations.py --new de     start de.json with every text to translate
    python dev_tools/check_translations.py --sync       add the missing texts (empty) to every
                                                        language file and drop the unused ones

The texts to translate are the first arguments of tr(), tr_n() (singular and plural) and
N_() in src/. An empty translation means "not translated yet": the English text is shown.

FAIL (exit code 1):
  - tr() / tr_n() / N_() called with something else than a plain string (an f-string or a
    variable cannot be found by this script: use placeholders, or tr_name() for names);
  - a translation whose {placeholders} differ from the English text;
  - a plural entry that is not a list with one text per plural form of the language
    (PLURAL_FORMS in src/i18n/__init__.py), or a JSON file that does not load;
  - a language file missing from LANGUAGES in src/i18n/__init__.py, or the reverse.
WARN:
  - texts not translated yet, translations no longer used;
  - plain English text passed to a Qt or Anki call without tr().
"""

import ast
import importlib.util
import json
import os
import re
import string
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "src")
I18N = os.path.join(SRC, "i18n")

TRANSLATE_CALLS = {"tr": 1, "tr_n": 2, "N_": 1}


def _i18n_module():
    """src/i18n/__init__.py, for LANGUAGES and the plural forms (it imports nothing at load)."""
    spec = importlib.util.spec_from_file_location("deep_dive_i18n", os.path.join(I18N, "__init__.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


I18N_MODULE = _i18n_module()
# Calls whose text arguments are shown to the user (positions of those arguments).
UI_CALLS = {
    "setText": (0,), "setToolTip": (0,), "setTitle": (0,), "setWindowTitle": (0,),
    "setPlaceholderText": (0,), "setStatusTip": (0,), "QLabel": (0,), "QPushButton": (0,),
    "QCheckBox": (0,), "QRadioButton": (0,), "QGroupBox": (0,), "QAction": (0,),
    "addAction": (0,), "addMenu": (0,), "addTab": (1,), "insertTab": (2,), "addItem": (0,),
    "addRow": (0,), "tooltip": (0,), "showInfo": (0,), "showWarning": (0,),
    "showCritical": (0,), "askUser": (0,), "question": (1, 2), "information": (1, 2),
    "warning": (1, 2), "critical": (1, 2), "getText": (1, 2), "getColor": (2,),
}
# Shown as is in every language.
NOT_TEXT = {"English", "GitHub", "Deep Dive", "Deep Dive Stats", "OK", "YRS"}


def _call_name(node):
    func = node.func
    if isinstance(func, ast.Attribute):
        return func.attr
    if isinstance(func, ast.Name):
        return func.id
    return ""


def _is_text(node):
    return isinstance(node, ast.Constant) and isinstance(node.value, str)


def scan_sources():
    """({english: [locations]}, {singular: plural}, errors, warnings)."""
    texts, plurals, errors, warnings = {}, {}, [], []
    for base, dirs, names in os.walk(SRC):
        dirs[:] = [d for d in dirs if d != "__pycache__"]
        for name in sorted(names):
            if not name.endswith(".py"):
                continue
            path = os.path.join(base, name)
            rel = os.path.relpath(path, ROOT).replace(os.sep, "/")
            with open(path, encoding="utf-8") as handle:
                tree = ast.parse(handle.read(), rel)
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call):
                    continue
                call = _call_name(node)
                where = f"{rel}:{node.lineno}"
                if call in TRANSLATE_CALLS and isinstance(node.func, ast.Name):
                    needed = TRANSLATE_CALLS[call]
                    args = node.args[:needed]
                    if len(args) < needed or not all(_is_text(a) for a in args):
                        errors.append(f"{where}: {call}() needs plain strings (use placeholders or tr_name)")
                        continue
                    texts.setdefault(args[0].value, []).append(where)
                    if call == "tr_n":
                        plurals[args[0].value] = args[1].value
                elif call in UI_CALLS:
                    for pos in UI_CALLS[call]:
                        if pos < len(node.args) and _is_text(node.args[pos]):
                            value = node.args[pos].value.strip()
                            if re.search(r"[A-Za-z]{2,}", value) and value not in NOT_TEXT:
                                warnings.append(f"{where}: not translated: {value[:60]!r}")
    return texts, plurals, errors, warnings


def placeholders(text):
    try:
        return {field for _lit, field, _spec, _conv in string.Formatter().parse(text) if field is not None}
    except ValueError:
        return None


def load_catalog(code):
    path = os.path.join(I18N, f"{code}.json")
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def languages():
    return sorted(f[:-5] for f in os.listdir(I18N) if f.endswith(".json"))


def check_catalog(code, texts, plurals):
    errors, warnings = [], []
    try:
        data = load_catalog(code)
    except (OSError, ValueError) as exc:
        return [f"{code}.json: does not load: {exc}"], []
    entries = {k: v for k, v in data.items() if not k.startswith("@")}
    for english in sorted(texts):
        value = entries.get(english)
        if english in plurals:
            forms = I18N_MODULE.plural_forms(code)
            want = placeholders(plurals[english]) | placeholders(english)
            if value in (None, "") or (isinstance(value, list) and not any(value)):
                warnings.append(f"{code}: not translated (plural): {english!r}")
                continue
            if not (isinstance(value, list) and len(value) == forms and all(isinstance(v, str) and v for v in value)):
                errors.append(f"{code}: plural must be a list of {forms} text(s): {english!r}")
                continue
            for form in value:
                # A form may leave the count out ("une carte"), never add another value.
                if not placeholders(form) <= want | {"n"}:
                    errors.append(f"{code}: placeholders differ: {english!r} -> {form!r}")
            continue
        if value in (None, ""):
            warnings.append(f"{code}: not translated: {english!r}")
            continue
        if not isinstance(value, str):
            errors.append(f"{code}: must be a text: {english!r}")
            continue
        if placeholders(value) != placeholders(english):
            errors.append(f"{code}: placeholders differ: {english!r} -> {value!r}")
    for english in sorted(set(entries) - set(texts)):
        warnings.append(f"{code}: no longer used: {english!r}")
    return errors, warnings


def write_catalog(code, texts, plurals, keep=None):
    keep = keep or {}
    data = {"@language": keep.get("@language", code)}
    for english in sorted(texts, key=lambda t: (t.lower(), t)):
        old = keep.get(english)
        if english in plurals:
            forms = I18N_MODULE.plural_forms(code)
            data[english] = old if isinstance(old, list) and len(old) == forms else [""] * forms
        else:
            data[english] = old if isinstance(old, str) else ""
    with open(os.path.join(I18N, f"{code}.json"), "w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


def main(argv):
    texts, plurals, errors, warnings = scan_sources()
    if "--new" in argv:
        code = argv[argv.index("--new") + 1]
        write_catalog(code, texts, plurals)
        print(f"src/i18n/{code}.json written with {len(texts)} texts to translate.")
        print("Add the language to LANGUAGES in src/i18n/__init__.py (and PLURAL_FORMS if it")
        print("does not have two forms, _NUMBER_STYLE for its numbers).")
        return 0
    if "--sync" in argv:
        for code in languages():
            write_catalog(code, texts, plurals, keep=load_catalog(code))
        print(f"{len(languages())} language file(s) synced with {len(texts)} texts.")
    known = set(I18N_MODULE.LANGUAGES)
    for code in sorted(known - set(languages())):
        errors.append(f"{code}: in LANGUAGES but src/i18n/{code}.json is missing")
    for code in sorted(set(languages()) - known):
        errors.append(f"{code}.json: not in LANGUAGES in src/i18n/__init__.py")
    for code in languages():
        e, w = check_catalog(code, texts, plurals)
        errors += e
        warnings += w
    for line in warnings:
        print("WARN", line)
    for line in errors:
        print("FAIL", line)
    print(f"{len(texts)} texts, {len(languages())} language(s): {len(errors)} errors, {len(warnings)} warnings.")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
