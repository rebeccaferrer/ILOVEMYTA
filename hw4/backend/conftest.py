"""Shared test setup: every test runs against a throwaway copy of the database, so the
real campus_customs.db is never touched, and they write to a throwaway audit trail. pytest loads this before any test module."""

from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path

HW_DIR = Path(__file__).resolve().parent.parent
TMP_DB = Path(tempfile.mkdtemp()) / "campus_customs.db"
shutil.copy2(HW_DIR / "data" / "data" / "campus_customs.db", TMP_DB)
os.environ["CC_DB_PATH"] = str(TMP_DB)  # must be set before the app modules are imported
TMP_AUDIT = TMP_DB.parent / "audit_trail.json"
os.environ["CC_AUDIT_PATH"] = str(TMP_AUDIT)  # tests never touch output/audit_trail.json
