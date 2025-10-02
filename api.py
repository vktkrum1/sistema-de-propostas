from flask import Blueprint, jsonify, request
import requests

api_bp = Blueprint('api_bp', __name__, url_prefix='/api')   # ← prefixo único

@api_bp.route('/cnpj/<cnpj>', methods=['GET'])
def consultar_cnpj(cnpj):
    cnpj = ''.join(filter(str.isdigit, cnpj))
    if len(cnpj) != 14:
        return jsonify(error='CNPJ inválido (14 dígitos).'), 400

    try:
        r = requests.get(f'https://publica.cnpj.ws/cnpj/{cnpj}', timeout=6)
        if r.status_code == 404:
            return jsonify(error='CNPJ não encontrado.'), 404
        r.raise_for_status()
        data = r.json()
        return jsonify(
            company  = data.get('razao_social', ''),
            cnpj     = data.get('cnpj', ''),
            email    = data.get('email', ''),
            telefone = data.get('ddd_telefone_1', '')
        )
    except requests.exceptions.RequestException as e:
        return jsonify(error='Erro ao consultar API externa.'), 502
