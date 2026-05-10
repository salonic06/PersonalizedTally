from __future__ import annotations

from pathlib import Path


def delete_invoice_excel_if_allowed(path: str, invoice_output_folder: str) -> tuple[bool, str]:
    """
    Delete an invoice .xlsx only if it exists and its resolved path lies under
    the resolved invoice output folder (safety: never delete arbitrary paths).

    Returns (success, message). success is True if the file is gone (deleted or
    already missing). success is False if the file exists but was not deleted.
    """
    raw = (path or "").strip()
    root_raw = (invoice_output_folder or "").strip()
    if not raw:
        return True, ""
    p = Path(raw)
    if not p.is_file():
        return True, ""

    if not root_raw:
        return False, "Set **Invoice output folder** in Settings before deleting files from disk."

    try:
        resolved_file = p.resolve()
        resolved_root = Path(root_raw).resolve()
    except OSError as e:
        return False, str(e)

    try:
        resolved_file.relative_to(resolved_root)
    except ValueError:
        return (
            False,
            "The stored path is not inside your invoice output folder, so the file was not deleted.",
        )

    try:
        resolved_file.unlink()
        return True, ""
    except OSError as e:
        return False, str(e)
