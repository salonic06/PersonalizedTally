from __future__ import annotations

from enum import Enum

from PySide6.QtWidgets import QMessageBox, QWidget


class TrashInvoiceChoice(Enum):
    CANCEL = 0
    DB_ONLY = 1
    """Soft delete — appears in Trash; Excel file kept on disk."""
    PERMANENT_DELETE_FILE = 2
    """Remove invoice from database permanently and delete Excel when allowed."""


def confirm_trash_invoice(parent: QWidget, *, has_excel_path: bool) -> TrashInvoiceChoice:
    """
    Ask how to remove an invoice. If there is no stored Excel path,
    only Cancel / Move to trash are offered.
    """
    box = QMessageBox(parent)
    box.setIcon(QMessageBox.Icon.Question)
    box.setWindowTitle("Remove invoice")
    box.setText(
        "Move this invoice to trash? It will disappear from dues and the ledger until you restore it."
    )
    if has_excel_path:
        box.setInformativeText(
            "**Move to trash only** — Excel file stays on disk; you can restore from Trash.\n\n"
            "**Delete invoice + Excel permanently** — removes the invoice from the database "
            "(it will not appear in Trash). Payment allocations to this invoice are removed. "
            "The Excel file is deleted only if it lies inside **Settings → Invoice output folder**."
        )

    btn_cancel = box.addButton(QMessageBox.StandardButton.Cancel)
    btn_cancel.setText("Cancel")
    btn_db = box.addButton("Move to trash only", QMessageBox.ButtonRole.ActionRole)
    btn_perm = None
    if has_excel_path:
        btn_perm = box.addButton(
            "Delete invoice + Excel permanently",
            QMessageBox.ButtonRole.DestructiveRole,
        )

    box.setDefaultButton(btn_db)
    box.exec()
    clicked = box.clickedButton()
    if clicked == btn_db:
        return TrashInvoiceChoice.DB_ONLY
    if has_excel_path and btn_perm is not None and clicked == btn_perm:
        return TrashInvoiceChoice.PERMANENT_DELETE_FILE
    return TrashInvoiceChoice.CANCEL


def confirm_invoice_permanent_delete(parent: QWidget, invoice_no: str) -> bool:
    """Second step: user must confirm irreversible database removal."""
    inv = invoice_no.strip() or "this invoice"
    return (
        QMessageBox.question(
            parent,
            "Confirm permanent delete",
            f"Permanently delete invoice {inv}?\n\n"
            "This cannot be undone. The invoice will not appear in Trash.\n"
            "Allocations from payments to this invoice will be removed.\n"
            "The Excel file will be deleted when possible.\n\n"
            "Continue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        == QMessageBox.StandardButton.Yes
    )
