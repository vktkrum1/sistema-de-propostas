from flask import Flask
from sqlalchemy import inspect, text

from models import db
from utils.schema import ensure_proposal_columns


def test_ensure_proposal_columns_adds_missing_columns():
    app = Flask(__name__)
    app.config.update(
        SQLALCHEMY_DATABASE_URI="sqlite://",
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
    )

    db.init_app(app)

    with app.app_context():
        engine = db.engine
        with engine.begin() as connection:
            connection.execute(
                text(
                    """
                    CREATE TABLE proposals (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        company VARCHAR(255)
                    )
                    """
                )
            )

        ensure_proposal_columns()

        inspector = inspect(engine)
        column_names = {column["name"] for column in inspector.get_columns("proposals")}

        assert {
            "enviar_email",
            "email_corpo",
            "email_cc",
            "sistema_ativo",
            "sistema_nome",
            "sistema_descricao",
            "sistema_imagem",
            "sistema_quantidade",
            "sistema_preco_unitario",
            "sistema_preco_total",
        }.issubset(column_names)

