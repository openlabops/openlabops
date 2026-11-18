#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
OpenLabOps Internationalization (i18n) Engine
Zero External Dependencies: 100% Python Standard Library [INV-01].
Loads localized strings from lang/{locale}.json.
"""

import os
import json
from pathlib import Path

def _is_openlab_context() -> bool:
    """Detect whether running in OpenLabOps (defaults to en_US)."""
    if os.getenv("LAB_MODE") == "1":
        return True
    here = Path(__file__).resolve()
    if "openlab" in str(here).lower():
        return True
    repo_root = here.parent.parent.parent.parent
    if (repo_root / "conf" / "openlab.manifest.yml").exists():
        return True
    return False


# Locales & Defaults
DEFAULT_LOCALE = "en_US" if _is_openlab_context() else "zh_TW"
SUPPORTED_LOCALES = ["en_US", "zh_TW", "ja_JP"]

_translations_cache = {}
_current_locale = None

def detect_system_locale():
    """Detect locale from explicit environment variables (LAB_LANG, LAB_LANG), persistent config files, or fallback to OS LANG"""
    # 1. 最高優先級：專案專用環境變數 (明確於終端指定覆寫)
    for env in ("LAB_LANG",):
        val = os.getenv(env)
        if val:
            val_clean = val.split(".")[0].strip()
            if val_clean in SUPPORTED_LOCALES:
                return val_clean
            if val_clean.startswith("zh"):
                return "zh_TW"
            if val_clean.startswith("ja"):
                return "ja_JP"
            if val_clean.startswith("en"):
                return "en_US"

    # 2. 專案固化語系檔案 (Persistent Locale State from lab-init / deploy-ops-tools)
    locale_files = [
        Path.home() / ".config" / "openlab" / "locale",
        Path.home() / ".config" / "openlab" / "locale",
        Path("/usr/local/etc/openlab/locale"),
        Path("/usr/local/etc/openlab/locale"),
        Path("/etc/openlab/locale"),
        Path("/etc/openlab/locale"),
    ]
    for lf in locale_files:
        if lf.exists():
            try:
                txt = lf.read_text(encoding="utf-8").strip().split(".")[0]
                if txt in SUPPORTED_LOCALES:
                    return txt
                if txt.startswith("zh"):
                    return "zh_TW"
                if txt.startswith("ja"):
                    return "ja_JP"
                if txt.startswith("en"):
                    return "en_US"
            except Exception:
                pass

    # 3. 工具宣告組態檔 (tools.config.json default_locale)
    for cfg_path in [
        Path.home() / "openlabops" / "tools" / "conf" / "tools.config.json",
        Path.home() / "openlabops" / "tools" / "conf" / "tools.config.json",
        Path("/usr/local/etc/openlab/conf/tools.config.json"),
        Path("/usr/local/etc/openlab/conf/tools.config.json"),
        Path("/usr/local/bin/openlab/conf/tools.config.json"),
        Path("/usr/local/bin/openlab/conf/tools.config.json"),
    ]:
        if cfg_path.exists():
            try:
                data = json.loads(cfg_path.read_text(encoding="utf-8"))
                loc = data.get("default_locale") or data.get("locale")
                if loc:
                    loc = loc.split(".")[0]
                    if loc in SUPPORTED_LOCALES:
                        return loc
                    if loc.startswith("zh"):
                        return "zh_TW"
                    if loc.startswith("ja"):
                        return "ja_JP"
                    if loc.startswith("en"):
                        return "en_US"
            except Exception:
                pass

    # 4. 站點宣告清單 (conf/openlab.manifest.yml 或 conf/openlab.manifest.yml)
    manifest_candidates = [
        Path.home() / "openlabops" / "conf" / "openlab.manifest.yml",
        Path.home() / "openlabops" / "conf" / "openlab.manifest.yml",
        Path("/workspace/conf/openlab.manifest.yml"),
        Path(__file__).resolve().parent.parent.parent.parent / "conf" / "openlab.manifest.yml",
        Path(__file__).resolve().parent.parent.parent.parent / "conf" / "openlab.manifest.yml",
    ]
    for m_path in manifest_candidates:
        if m_path.exists():
            try:
                for line in m_path.read_text(encoding="utf-8").splitlines():
                    line = line.strip()
                    if line.startswith("locale:") or line.startswith("lang:"):
                        val = line.split(":", 1)[1].strip().strip('"').strip("'").split(".")[0]
                        if val in SUPPORTED_LOCALES:
                            return val
                        if val.startswith("zh"):
                            return "zh_TW"
                        if val.startswith("ja"):
                            return "ja_JP"
                        if val.startswith("en"):
                            return "en_US"
            except Exception:
                pass

    # 5. 回退至作業系統通用環境變數 (LC_ALL, LANG)
    for env in ("LC_ALL", "LANG"):
        val = os.getenv(env)
        if val:
            val_clean = val.split(".")[0].strip()
            if val_clean in SUPPORTED_LOCALES:
                return val_clean
            if val_clean.startswith("zh"):
                return "zh_TW"
            if val_clean.startswith("ja"):
                return "ja_JP"
            if val_clean.startswith("en"):
                return "en_US"

    return DEFAULT_LOCALE

def get_locale():
    global _current_locale
    if not _current_locale:
        _current_locale = detect_system_locale()
    return _current_locale

def set_locale(locale: str):
    global _current_locale
    if locale in SUPPORTED_LOCALES:
        _current_locale = locale
    else:
        for sup in SUPPORTED_LOCALES:
            if sup.startswith(locale[:2]):
                _current_locale = sup
                break
        else:
            _current_locale = DEFAULT_LOCALE
    os.environ["LAB_LANG"] = _current_locale
    os.environ["LAB_LANG"] = _current_locale

def find_lang_dir():
    """Locates lang/ directory across known project roots"""
    candidates = [
        Path(__file__).resolve().parent.parent.parent.parent / "lang",
        Path(__file__).resolve().parent.parent.parent / "lang",
        Path("/workspace/lang"),
        Path.home() / "openlabops" / "lang",
        Path.home() / "openlabops" / "lang",
        Path("/usr/local/bin/openlab/lang"),
        Path("/usr/local/bin/openlab/lang"),
        Path("/usr/local/etc/openlab/lang"),
        Path("/usr/local/etc/openlab/lang")
    ]
    for c in candidates:
        if c.exists() and (c / "zh_TW.json").exists():
            return c
    return candidates[0]

def load_translations(locale: str):
    if locale in _translations_cache:
        return _translations_cache[locale]

    lang_dir = find_lang_dir()
    lang_file = lang_dir / f"{locale}.json"

    if not lang_file.exists():
        lang_file = lang_dir / f"{DEFAULT_LOCALE}.json"

    if lang_file.exists():
        try:
            data = json.loads(lang_file.read_text(encoding="utf-8"))
            _translations_cache[locale] = data
            return data
        except Exception:
            pass

    _translations_cache[locale] = {}
    return {}

def t(keypath: str, default: str = None, **kwargs) -> str:
    """
    Look up translation by dot-separated path (e.g. 'common.success', 'errors.node_unreachable')
    Supports keyword interpolation: t('errors.node_unreachable', target='192.168.1.1')
    """
    locale = get_locale()
    dict_data = load_translations(locale)

    parts = keypath.split(".")
    val = dict_data
    for p in parts:
        if isinstance(val, dict) and p in val:
            val = val[p]
        else:
            val = None
            break

    if val is None:
        # Fallback to English
        if locale != "en_US":
            en_dict = load_translations("en_US")
            en_val = en_dict
            for p in parts:
                if isinstance(en_val, dict) and p in en_val:
                    en_val = en_val[p]
                else:
                    en_val = None
                    break
            if en_val is not None:
                val = en_val

    if val is None:
        val = default if default is not None else keypath

    if kwargs and isinstance(val, str):
        try:
            return val.format(**kwargs)
        except Exception:
            return val

    return str(val)

