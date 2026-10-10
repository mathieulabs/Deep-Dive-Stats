# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
import os
import sys
import logging
import re
import traceback
from datetime import datetime, timedelta
from logging.handlers import MemoryHandler, RotatingFileHandler

class DeepDiveLogger:
    _logger = None
    _memory_handler = None
    LOG_RETENTION_DAYS = 3

    @classmethod
    def get_logger(cls):
        if cls._logger is None:
            cls._setup_logger()
        return cls._logger

    @classmethod
    def _get_log_dir(cls):
        # src/details/logic/logger.py -> src -> addon root
        addon_path = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
            os.path.abspath(__file__)
        ))))
        log_dir = os.path.join(addon_path, "user_files")
        if not os.path.exists(log_dir):
            os.makedirs(log_dir, exist_ok=True)
        return log_dir

    @classmethod
    def _get_log_file(cls):
        return os.path.join(cls._get_log_dir(), "debug.log")

    @classmethod
    def _trim_old_logs(cls):
        """Remove log lines older than LOG_RETENTION_DAYS from the single log file."""
        log_file = cls._get_log_file()
        if not os.path.exists(log_file):
            return
        try:
            cutoff = datetime.now() - timedelta(days=cls.LOG_RETENTION_DAYS)
            kept_lines = []
            with open(log_file, "r", encoding="utf-8", errors="replace") as f:
                for line in f:
                    try:
                        date_str = line[1:20]
                        line_date = datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S")
                        if line_date >= cutoff:
                            kept_lines.append(line)
                    except (ValueError, IndexError):
                        kept_lines.append(line)
            with open(log_file, "w", encoding="utf-8") as f:
                f.writelines(kept_lines)
        except Exception:
            pass

    @classmethod
    def clear_logs(cls):
        """Truncate the log file."""
        log_file = cls._get_log_file()
        try:
            with open(log_file, "w", encoding="utf-8") as f:
                f.write(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [INFO] [CLEANUP] User cleared logs.\n")
            # Also drop the rotated copy so "clear" really clears everything.
            old_file = log_file + ".1"
            if os.path.exists(old_file):
                os.remove(old_file)
        except Exception:
            pass

    @classmethod
    def flush(cls):
        """Force any buffered log records to disk (call before reading the
        log file, and on shutdown so buffered lines aren't lost)."""
        try:
            if cls._memory_handler is not None:
                cls._memory_handler.flush()
        except Exception:
            pass

    @classmethod
    def _setup_logger(cls):
        log_file = cls._get_log_file()

        cls._trim_old_logs()

        cls._logger = logging.getLogger("DeepDiveStats")
        # INFO and above are written; DEBUG records are dropped at this level.
        cls._logger.setLevel(logging.INFO)
        # Keep these records out of Anki's own handlers: only debug.log gets them.
        cls._logger.propagate = False

        # Capped at ~1 MB (+ one rotated copy), so a runaway log can never fill the disk.
        handler = RotatingFileHandler(
            log_file, maxBytes=1_000_000, backupCount=1, encoding="utf-8", delay=True
        )
        formatter = logging.Formatter(
            '[%(asctime)s] [%(levelname)s] %(message)s',
            '%Y-%m-%d %H:%M:%S'
        )
        handler.setFormatter(formatter)

        # A bare FileHandler flushes to disk on every emit, which blocks whichever thread logs.
        # Buffer up to 200 records in memory and write in batches, or immediately on WARNING and
        # above (rare, and the lines worth keeping if Anki crashes right after).
        buffered_handler = MemoryHandler(
            capacity=200,
            flushLevel=logging.WARNING,
            target=handler,
        )
        cls._memory_handler = buffered_handler

        if not cls._logger.handlers:
            cls._logger.addHandler(buffered_handler)

    _redact_paths = None

    @classmethod
    def _build_redact_paths(cls):
        subs = []
        addon_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
            os.path.abspath(__file__)
        ))))
        home = os.path.expanduser("~")
        for raw, repl in ((addon_root, "<addon>"), (home, "~")):
            if raw and len(raw) > 2:
                for variant in {raw, raw.replace("\\", "/"), raw.replace("/", "\\")}:
                    subs.append((variant, repl))
        # Longest first so "<addon>" wins over the shorter home prefix.
        subs.sort(key=lambda x: -len(x[0]))
        return subs, home

    @staticmethod
    def _replace_word(text, word, repl):
        """Replace `word` only where it is a whole word, so a short name does not damage other words."""
        if not word:
            return text
        return re.sub(r"(?<!\w)" + re.escape(word) + r"(?!\w)", repl, text)

    @classmethod
    def _redact(cls, text):
        """Strip personal details so a log can be pasted into a public issue:
        the user's home folder / account name, the add-on folder and the
        Anki profile name are replaced by placeholders."""
        try:
            text = str(text)
            cached = cls._redact_paths
            if cached is None:
                cached = cls._redact_paths = cls._build_redact_paths()
            subs, home = cached
            try:
                from aqt import mw

                profile = getattr(getattr(mw, "pm", None), "name", None)
            except Exception:
                profile = None
            for raw, repl in subs:
                text = text.replace(raw, repl)
            if profile and len(str(profile)) > 1:
                cleaned = "".join(c for c in str(profile) if c.isalnum() or c in " ._-").strip()
                for name in {str(profile), cleaned}:
                    text = cls._replace_word(text, name, "<profile>")
            user = os.path.basename(home.rstrip("/\\"))
            if user and len(user) > 2:
                text = cls._replace_word(text, user, "<user>")
        except Exception:
            pass
        return text

    @classmethod
    def log(cls, message, level="INFO", tag="GENERAL"):
        logger = cls.get_logger()

        lvl = str(level or "INFO").upper()

        # Debug records are dropped by the logger level: don't pay for the redaction.
        if lvl == "DEBUG" and not logger.isEnabledFor(logging.DEBUG):
            return

        msg = cls._redact(f"[{tag}] {message}")

        if lvl == "DEBUG":
            logger.debug(msg)
        elif lvl == "WARNING":
            logger.warning(msg)
        elif lvl == "ERROR":
            logger.error(msg)
        else:
            logger.info(msg)


def log_debug(message, tag="DEBUG"):
    DeepDiveLogger.log(message, level="DEBUG", tag=tag)

def log_info(message, tag="INFO"):
    DeepDiveLogger.log(message, level="INFO", tag=tag)

def log_warn(message, tag="WARN"):
    DeepDiveLogger.log(message, level="WARNING", tag=tag)

def _with_traceback(message):
    """When called from an except block, append the last frames of the exception
    so an error line says where it came from, not only what it said."""
    try:
        etype, exc, tb = sys.exc_info()
        if exc is None or "Traceback" in str(message):
            return message
        trace = "".join(traceback.format_exception(etype, exc, tb, limit=-3)).rstrip()
        return f"{message}\n{trace}"
    except Exception:
        return message


def log_error(message, tag="ERROR"):
    DeepDiveLogger.log(_with_traceback(message), level="ERROR", tag=tag)


_IGNORED_SITES = set()


def log_swallowed():
    """Log an exception the caller is ignoring, once per call site.

    Call it inside an except block instead of pass, so a hidden failure still
    leaves one line in debug.log.
    """
    try:
        etype, exc, tb = sys.exc_info()
        if exc is None:
            return
        # Cheap key first: this runs on every swallowed exception, including ones
        # raised repeatedly, so don't build a traceback just to find out we've seen it.
        site = (tb.tb_frame.f_code.co_filename, tb.tb_lineno) if tb is not None else (None, None)
        if site in _IGNORED_SITES:
            return
        _IGNORED_SITES.add(site)
        where = f"{os.path.basename(site[0] or '?')}:{site[1]}"
        trace = "".join(traceback.format_exception(etype, exc, tb, limit=-3)).rstrip()
        log_warn(f"Ignored {etype.__name__} at {where}: {exc}\n{trace}", tag="IGNORED")
    except Exception:
        pass
