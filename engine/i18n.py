#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
OpenLabOps Internationalization (i18n) Engine Bridge
Delegates directly to tools/lib/core/i18n.py as Single Source of Truth [INV-01].
"""

import sys
from pathlib import Path

_CORE_LIB = Path(__file__).resolve().parent.parent / "tools" / "lib"
if str(_CORE_LIB) not in sys.path:
    sys.path.insert(0, str(_CORE_LIB))

from core.i18n import (  # noqa: E402, F401
    DEFAULT_LOCALE,
    SUPPORTED_LOCALES,
    detect_system_locale,
    get_locale,
    set_locale,
    find_lang_dir,
    load_translations,
    t,
)

