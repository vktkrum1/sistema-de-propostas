"""Database compatibility helpers."""
from __future__ import annotations

from contextlib import suppress

from flask import current_app, has_app_context
from sqlalchemy import inspect, text
from sqlalchemy.exc import OperationalError

from models import db


def ensure_proposal_columns() -> None:
    """Ensure legacy databases have the required proposal columns."""

    engine = db.engine
    inspector = inspect(engine)

    if "proposals" not in inspector.get_table_names():
        return

    existing_columns = {column["name"] for column in inspector.get_columns("proposals")}

    statements: list[tuple[str, str]] = []

    def ensure(column: str, ddl: str):
        if column not in existing_columns:
            statements.append((column, ddl))

    ensure(
        "enviar_email",
        "ALTER TABLE proposals ADD COLUMN enviar_email BOOLEAN NOT NULL DEFAULT 0",
    )
    ensure(
        "email_corpo",
        "ALTER TABLE proposals ADD COLUMN email_corpo TEXT NOT NULL DEFAULT ''",
    )
    ensure(
        "email_cc",
        "ALTER TABLE proposals ADD COLUMN email_cc TEXT NOT NULL DEFAULT ''",
    )
    ensure(
        "sistema_ativo",
        "ALTER TABLE proposals ADD COLUMN sistema_ativo BOOLEAN NOT NULL DEFAULT 0",
    )
    ensure(
        "sistema_nome",
        "ALTER TABLE proposals ADD COLUMN sistema_nome VARCHAR(128)",
    )
    ensure(
        "sistema_descricao",
        "ALTER TABLE proposals ADD COLUMN sistema_descricao TEXT",
    )
    ensure(
        "sistema_imagem",
        "ALTER TABLE proposals ADD COLUMN sistema_imagem VARCHAR(256)",
    )
    ensure(
        "sistema_quantidade",
        "ALTER TABLE proposals ADD COLUMN sistema_quantidade INTEGER",
    )
    ensure(
        "sistema_preco_unitario",
        "ALTER TABLE proposals ADD COLUMN sistema_preco_unitario FLOAT",
    )
    ensure(
        "sistema_preco_total",
        "ALTER TABLE proposals ADD COLUMN sistema_preco_total FLOAT",
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
            "Garantidas colunas ausentes na tabela proposals: %s",
            ", ".join(sorted(ensured_columns)),
        )

