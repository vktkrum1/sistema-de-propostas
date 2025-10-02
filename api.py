from __future__ import annotations

import json
from socket import timeout as SocketTimeout
from typing import Callable

from flask import Blueprint, jsonify, request
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

api_bp = Blueprint('api_bp', __name__, url_prefix='/api')   # ← prefixo único


class _CNPJNotFoundError(Exception):
    """Erro levantado quando o CNPJ não é encontrado na API pública."""


class _CNPJServiceError(Exception):
    """Erro genérico para falhas na comunicação/decodificação da API."""


def _fetch_cnpj_payload(
    cnpj: str,
    *,
    opener: Callable[[Request, float], object] = urlopen,
    timeout: float = 6,
) -> dict:
    """Consulta a API de CNPJ usando apenas a biblioteca padrão.

    Parameters
    ----------
    cnpj:
        Número do CNPJ normalizado (somente dígitos).
    opener:
        Função compatível com ``urllib.request.urlopen`` usada para facilitar testes.
    timeout:
        Tempo limite da requisição, em segundos.

    Returns
    -------
    dict
        Conteúdo JSON retornado pela API pública.
    """

    req = Request(
        f'https://publica.cnpj.ws/cnpj/{cnpj}',
        headers={'Accept': 'application/json'}
    )

    try:
        with opener(req, timeout=timeout) as resp:  # type: ignore[arg-type]
            payload = resp.read()
            headers = getattr(resp, 'headers', None)
            charset = None
            if headers is not None and hasattr(headers, 'get_content_charset'):
                charset = headers.get_content_charset()
    except HTTPError as exc:
        if exc.code == 404:
            raise _CNPJNotFoundError from exc
        raise _CNPJServiceError from exc
    except (URLError, SocketTimeout) as exc:
        raise _CNPJServiceError from exc

    if not charset:
        charset = 'utf-8'

    try:
        text = payload.decode(charset)
    except (LookupError, UnicodeDecodeError) as exc:
        raise _CNPJServiceError from exc

    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise _CNPJServiceError from exc


@api_bp.route('/cnpj/<cnpj>', methods=['GET'])
def consultar_cnpj(cnpj):
    cnpj = ''.join(filter(str.isdigit, cnpj))
    if len(cnpj) != 14:
        return jsonify(error='CNPJ inválido (14 dígitos).'), 400

    try:
        data = _fetch_cnpj_payload(cnpj)
    except _CNPJNotFoundError:
        return jsonify(error='CNPJ não encontrado.'), 404
    except _CNPJServiceError:
        return jsonify(error='Erro ao consultar API externa.'), 502

    return jsonify(
        company=data.get('razao_social', ''),
        cnpj=data.get('cnpj', ''),
        email=data.get('email', ''),
        telefone=data.get('ddd_telefone_1', '')
    )
