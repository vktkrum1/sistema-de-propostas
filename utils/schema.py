"""Database compatibility helpers."""
from __future__ import annotations

from contextlib import suppress

from flask import current_app, has_app_context
from sqlalchemy import inspect, text
from sqlalchemy.exc import OperationalError

from models import db


def ensure_proposal_email_columns() -> None:
    """Ensure legacy databases have the proposal email columns."""

    engine = db.engine
    inspector = inspect(engine)

    if "proposals" not in inspector.get_table_names():
        return

    existing_columns = {column["name"] for column in inspector.get_columns("proposals")}

    statements: list[tuple[str, str]] = []

    if "enviar_email" not in existing_columns:
        statements.append(
            (
                "enviar_email",
                "ALTER TABLE proposals ADD COLUMN enviar_email BOOLEAN NOT NULL DEFAULT 0",
            )
        )
    if "email_corpo" not in existing_columns:
        statements.append(
            (
                "email_corpo",
                "ALTER TABLE proposals ADD COLUMN email_corpo TEXT NOT NULL DEFAULT ''",
            )
        )
    if "email_cc" not in existing_columns:
        statements.append(
            (
                "email_cc",
                "ALTER TABLE proposals ADD COLUMN email_cc TEXT NOT NULL DEFAULT ''",
            )
        )

    if not statements:
        return

    with engine.begin() as connection:
        for _, statement in statements:
            with suppress(OperationalError):
                connection.execute(text(statement))

    ensured_columns = {
        column
        for column, _ in statements
        if column in {col["name"] for col in inspect(engine).get_columns("proposals")}
    }

    if ensured_columns and has_app_context():
        current_app.logger.info(
            "Garantidas colunas de e-mail na tabela proposals: %s",
            ", ".join(sorted(ensured_columns)),
        )

