import json
from datetime import datetime
from flask import Blueprint, request, jsonify, Response
from app import db
from app.models import Client, Scope, Token, Log, AuthorizationCode, SimulatedError
from app.utils import log_request

api_bp = Blueprint('api', __name__)

@api_bp.route('/clients', methods=['GET'])
def list_clients():
    clients = Client.query.order_by(Client.created_at.desc()).all()
    return jsonify([c.to_dict() for c in clients])

@api_bp.route('/clients', methods=['POST'])
def create_client():
    data = request.get_json() or request.form
    
    if not data.get('name'):
        return jsonify({'error': 'Name is required'}), 400
    if not data.get('redirect_uris'):
        return jsonify({'error': 'Redirect URIs are required'}), 400
    
    client = Client(
        name=data['name'],
        description=data.get('description', ''),
        redirect_uris=','.join(data['redirect_uris']) if isinstance(data['redirect_uris'], list) else data['redirect_uris'],
        grant_types=','.join(data.get('grant_types', ['authorization_code', 'client_credentials'])),
        token_format=data.get('token_format', 'jwt'),
        token_expire_seconds=int(data.get('token_expire_seconds', 3600)),
        require_consent=data.get('require_consent', True)
    )
    
    db.session.add(client)
    db.session.commit()
    
    log_request(
        'client_create',
        client_id=client.client_id,
        success=True
    )
    
    return jsonify(client.to_dict(include_secret=True)), 201

@api_bp.route('/clients/<int:client_id>', methods=['GET'])
def get_client(client_id):
    client = Client.query.get_or_404(client_id)
    return jsonify(client.to_dict())

@api_bp.route('/clients/<int:client_id>', methods=['PUT'])
def update_client(client_id):
    client = Client.query.get_or_404(client_id)
    data = request.get_json() or request.form
    
    if 'name' in data:
        client.name = data['name']
    if 'description' in data:
        client.description = data['description']
    if 'redirect_uris' in data:
        client.redirect_uris = ','.join(data['redirect_uris']) if isinstance(data['redirect_uris'], list) else data['redirect_uris']
    if 'grant_types' in data:
        client.grant_types = ','.join(data['grant_types']) if isinstance(data['grant_types'], list) else data['grant_types']
    if 'token_format' in data:
        client.token_format = data['token_format']
    if 'token_expire_seconds' in data:
        client.token_expire_seconds = int(data['token_expire_seconds'])
    if 'require_consent' in data:
        client.require_consent = data['require_consent']
    if 'is_active' in data:
        client.is_active = data['is_active']
    
    db.session.commit()
    
    log_request(
        'client_update',
        client_id=client.client_id,
        success=True
    )
    
    return jsonify(client.to_dict())

@api_bp.route('/clients/<int:client_id>', methods=['DELETE'])
def delete_client(client_id):
    client = Client.query.get_or_404(client_id)
    
    Token.query.filter_by(client_id=client.client_id).delete()
    AuthorizationCode.query.filter_by(client_id=client.client_id).delete()
    
    db.session.delete(client)
    db.session.commit()
    
    log_request(
        'client_delete',
        client_id=client.client_id,
        success=True
    )
    
    return '', 204

@api_bp.route('/scopes', methods=['GET'])
def list_scopes():
    scopes = Scope.query.order_by(Scope.created_at.desc()).all()
    return jsonify([s.to_dict() for s in scopes])

@api_bp.route('/scopes', methods=['POST'])
def create_scope():
    data = request.get_json() or request.form
    
    if not data.get('name'):
        return jsonify({'error': 'Name is required'}), 400
    
    if Scope.query.filter_by(name=data['name']).first():
        return jsonify({'error': 'Scope already exists'}), 400
    
    scope = Scope(
        name=data['name'],
        description=data.get('description', ''),
        is_enabled=data.get('is_enabled', True)
    )
    
    db.session.add(scope)
    db.session.commit()
    
    return jsonify(scope.to_dict()), 201

@api_bp.route('/scopes/<int:scope_id>', methods=['PUT'])
def update_scope(scope_id):
    scope = Scope.query.get_or_404(scope_id)
    data = request.get_json() or request.form
    
    if 'name' in data:
        scope.name = data['name']
    if 'description' in data:
        scope.description = data['description']
    if 'is_enabled' in data:
        scope.is_enabled = data['is_enabled']
    
    db.session.commit()
    return jsonify(scope.to_dict())

@api_bp.route('/scopes/<int:scope_id>', methods=['DELETE'])
def delete_scope(scope_id):
    scope = Scope.query.get_or_404(scope_id)
    db.session.delete(scope)
    db.session.commit()
    return '', 204

@api_bp.route('/tokens', methods=['GET'])
def list_tokens():
    tokens = Token.query.order_by(Token.created_at.desc()).limit(100).all()
    return jsonify([t.to_dict(include_token=False) for t in tokens])

@api_bp.route('/tokens/<int:token_id>/revoke', methods=['POST'])
def revoke_token(token_id):
    token = Token.query.get_or_404(token_id)
    token.is_revoked = True
    db.session.commit()
    
    log_request(
        'token_revoke',
        client_id=token.client_id,
        user_id=token.user_id,
        success=True
    )
    
    return jsonify({'message': 'Token revoked'})

@api_bp.route('/export/clients', methods=['GET'])
def export_clients():
    clients = Client.query.all()
    data = {
        'exported_at': datetime.utcnow().isoformat(),
        'clients': [c.to_dict(include_secret=True) for c in clients]
    }
    
    return Response(
        json.dumps(data, indent=2),
        mimetype='application/json',
        headers={'Content-Disposition': 'attachment; filename=oauth_clients.json'}
    )

@api_bp.route('/export/tokens', methods=['GET'])
def export_tokens():
    tokens = Token.query.all()
    data = {
        'exported_at': datetime.utcnow().isoformat(),
        'tokens': [t.to_dict(include_token=True) for t in tokens]
    }
    
    return Response(
        json.dumps(data, indent=2),
        mimetype='application/json',
        headers={'Content-Disposition': 'attachment; filename=oauth_tokens.json'}
    )

@api_bp.route('/export/all', methods=['GET'])
def export_all():
    clients = Client.query.all()
    tokens = Token.query.all()
    scopes = Scope.query.all()
    auth_codes = AuthorizationCode.query.all()
    logs = Log.query.all()
    simulated_errors = SimulatedError.query.all()
    
    data = {
        'exported_at': datetime.utcnow().isoformat(),
        'version': '1.0',
        'clients': [c.to_dict(include_secret=True) for c in clients],
        'tokens': [t.to_dict(include_token=True) for t in tokens],
        'scopes': [s.to_dict() for s in scopes],
        'authorization_codes': [ac.to_dict() for ac in auth_codes],
        'logs': [l.to_dict() for l in logs],
        'simulated_errors': [se.to_dict() for se in simulated_errors]
    }
    
    return Response(
        json.dumps(data, indent=2),
        mimetype='application/json',
        headers={'Content-Disposition': 'attachment; filename=oauth_server_full_export.json'}
    )
