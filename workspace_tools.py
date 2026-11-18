"""
title: Spark Workspace
description: Search local notes and explore CSV datasets on the Spark.
version: 0.1.0
"""

import csv
import math
import os
from pathlib import Path
import statistics

WORKSPACE = Path(os.getenv("SPARK_WORKSPACE") or (
    Path(__file__).resolve().parent / "workspace" if "__file__" in globals() else "/workspace"
))
MAX_BYTES = 2_000_000


def _path(filename: str) -> Path:
    path = (WORKSPACE / filename).resolve()
    if not path.is_relative_to(WORKSPACE.resolve()):
        raise ValueError("Choose a file inside workspace/.")
    if not path.is_file():
        raise ValueError("File not found. Use list_files first.")
    if path.stat().st_size > MAX_BYTES:
        raise ValueError("This example supports files up to 2 MB.")
    return path


def list_files() -> list[str]:
    """List up to 100 visible files in workspace/, including notes and CSV files."""
    files = []
    for path in sorted(WORKSPACE.rglob("*")):
        relative = path.relative_to(WORKSPACE)
        if any(part.startswith(".") for part in relative.parts):
            continue
        if path.is_file() and path.resolve().is_relative_to(WORKSPACE.resolve()):
            files.append(relative.as_posix())
        if len(files) == 100:
            break
    return files


def read_file(filename: str) -> dict:
    """Read a local text/Markdown file, with its filename and a truncation flag.

    :param filename: Relative filename from list_files.
    """
    try:
        with _path(filename).open(encoding="utf-8-sig") as source:
            text = source.read(20_001)
        return {"filename": filename, "content": text[:20_000], "truncated": len(text) > 20_000}
    except (ValueError, OSError, UnicodeError) as exc:
        return {"error": str(exc)}


def search_notes(query: str) -> dict:
    """Search local text/Markdown notes for a literal phrase; return matching lines and filenames.

    :param query: Word or phrase to search for, ignoring case.
    """
    if not query.strip():
        return {"error": "Provide a word or phrase to search for."}
    matches = []
    skipped = []
    for filename in list_files():
        if Path(filename).suffix.lower() not in {".txt", ".md", ".rst"}:
            continue
        try:
            with _path(filename).open(encoding="utf-8-sig") as source:
                for number, line in enumerate(source, start=1):
                    if query.casefold() in line.casefold():
                        matches.append({"filename": filename, "line": number, "text": line.strip()[:500]})
                        if len(matches) == 20:
                            return {"matches": matches, "limit_reached": True, "skipped_files": skipped}
        except (ValueError, OSError, UnicodeError):
            skipped.append(filename)
    return {"matches": matches, "limit_reached": False, "skipped_files": skipped}


def _csv(filename: str) -> tuple[list[str], list[dict]]:
    path = _path(filename)
    if path.suffix.lower() != ".csv":
        raise ValueError("Choose a .csv file from list_files.")
    with path.open(newline="", encoding="utf-8-sig") as source:
        reader = csv.DictReader(source)
        columns = reader.fieldnames
        if not columns or any(not column for column in columns) or len(set(columns)) != len(columns):
            raise ValueError("CSV needs a header row with unique, nonempty column names.")
        rows = []
        for row in reader:
            if None in row or any(value is None for value in row.values()):
                raise ValueError("CSV has a row with a different number of fields from its header.")
            rows.append(row)
            if len(rows) > 50_000:
                raise ValueError("This example supports CSVs up to 50,000 rows.")
    return columns, rows


def inspect_csv(filename: str) -> dict:
    """Return CSV column names, total row count, and the first five rows.

    :param filename: Relative CSV filename from list_files.
    """
    try:
        columns, rows = _csv(filename)
        return {"filename": filename, "columns": columns, "row_count": len(rows), "preview": rows[:5]}
    except (ValueError, OSError, UnicodeError, csv.Error) as exc:
        return {"error": str(exc)}


def summarise_csv(filename: str, column: str) -> dict:
    """Calculate count, missing/invalid counts, mean, median, min, max, and sample standard deviation.

    :param filename: Relative CSV filename from list_files.
    :param column: Exact numeric column name, as returned by inspect_csv.
    """
    try:
        columns, rows = _csv(filename)
        if column not in columns:
            return {"error": "Column not found.", "available_columns": columns}
        values = []
        missing = invalid = 0
        for row in rows:
            cell = row[column].strip()
            if not cell:
                missing += 1
                continue
            try:
                value = float(cell)
                if not math.isfinite(value):
                    raise ValueError("Non-finite number")
                values.append(value)
            except ValueError:
                invalid += 1
        return {
            "filename": filename, "column": column, "row_count": len(rows),
            "numeric_count": len(values), "missing_count": missing, "invalid_count": invalid,
            "mean": statistics.mean(values) if values else None,
            "median": statistics.median(values) if values else None,
            "min": min(values) if values else None,
            "max": max(values) if values else None,
            "sample_stddev": statistics.stdev(values) if len(values) > 1 else None,
        }
    except (ValueError, OSError, UnicodeError, csv.Error) as exc:
        return {"error": str(exc)}


# Open WebUI loads this class. The Python agent uses the same functions above.
class Tools:
    async def list_files(self) -> list[str]:
        """List local workspace files, including notes and CSVs."""
        return list_files()

    async def read_file(self, filename: str) -> dict:
        """Read a local text/Markdown file.

        :param filename: Relative filename from list_files.
        """
        return read_file(filename)

    async def search_notes(self, query: str) -> dict:
        """Search text/Markdown notes and return matching lines with filenames.

        :param query: Word or phrase to search for, ignoring case.
        """
        return search_notes(query)

    async def inspect_csv(self, filename: str) -> dict:
        """Get CSV column names, row count, and a five-row preview.

        :param filename: Relative CSV filename from list_files.
        """
        return inspect_csv(filename)

    async def summarise_csv(self, filename: str, column: str) -> dict:
        """Calculate numeric summary statistics, reporting missing and invalid values.

        :param filename: Relative CSV filename from list_files.
        :param column: Exact numeric column name from inspect_csv.
        """
        return summarise_csv(filename, column)
