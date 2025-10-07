"""System catalog and helpers for proposal forms."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, Optional
from types import SimpleNamespace


@dataclass(frozen=True)
class SystemOption:
    """Represents a selectable system template."""

    key: str
    label: str
    description: str
    image: str
    default_quantity: int
    unit_price: float

    def to_dict(self) -> dict:
        return {
            "key": self.key,
            "label": self.label,
            "description": self.description,
            "image": self.image,
            "default_quantity": self.default_quantity,
            "unit_price": self.unit_price,
        }


SYSTEM_OPTIONS: Dict[str, SystemOption] = {
    "rhid": SystemOption(
        key="rhid",
        label="RHiD",
        description="Plataforma RHiD para gestão completa de Recursos Humanos.",
        image="static/images/rhid.png",
        default_quantity=1,
        unit_price=0.0,
    ),
    "sollus_access": SystemOption(
        key="sollus_access",
        label="Sollus Access",
        description="Sollus Access - controle de acesso integrado e inteligente.",
        image="static/images/sem-imagem.png",
        default_quantity=1,
        unit_price=0.0,
    ),
    "velti_ponto": SystemOption(
        key="velti_ponto",
        label="Velti Ponto",
        description="Velti Ponto para monitoramento eletrônico da jornada.",
        image="static/images/sem-imagem.png",
        default_quantity=1,
        unit_price=0.0,
    ),
    "henry_ponto": SystemOption(
        key="henry_ponto",
        label="Henry Ponto",
        description="Henry Ponto homologado para controle de ponto.",
        image="static/images/sem-imagem.png",
        default_quantity=1,
        unit_price=0.0,
    ),
    "secullum": SystemOption(
        key="secullum",
        label="Secullum",
        description="Secullum - plataforma para gestão de ponto e acesso.",
        image="static/images/sem-imagem.png",
        default_quantity=1,
        unit_price=0.0,
    ),
}


def iter_system_options() -> Iterable[SystemOption]:
    return SYSTEM_OPTIONS.values()


def get_system_option(key: Optional[str]) -> Optional[SystemOption]:
    if not key:
        return None
    return SYSTEM_OPTIONS.get(key)


def build_system_item(
    option: SystemOption,
    quantity: Optional[int] = None,
    unit_price: Optional[float] = None,
):
    qty = option.default_quantity if quantity is None else max(1, quantity)
    price = option.unit_price if unit_price is None else max(0.0, unit_price)

    return SimpleNamespace(
        id=f"system:{option.key}",
        name=option.label,
        description=option.description,
        illustration_path=option.image,
        quantity=qty,
        unit_price=price,
        discount_percent=0.0,
    )


def serialize_system_payload(option: SystemOption, quantity: int, unit_price: float) -> dict:
    return {
        "key": option.key,
        "quantity": int(quantity),
        "unit_price": float(unit_price),
    }


def parse_unit_price(value: str) -> float:
    if not value:
        return 0.0
    normalized = value.strip()
    if not normalized:
        return 0.0
    normalized = normalized.replace("R$", "").strip()
    normalized = normalized.replace(".", "").replace(",", ".")
    try:
        return float(normalized)
    except ValueError:
        return 0.0
