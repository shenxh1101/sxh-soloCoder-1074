import json
from flask import Blueprint, request, jsonify, Response, current_app
from app import db
from app.models import Client, Scope, Token, Log, AuthorizationCode, SimulatedError, utcnow
from app.utils import log_request, validate_token

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
        'exported_at': utcnow().isoformat(),
        'version': '1.0',
        'clients': [c.to_dict(include_secret=True) for c in clients]
    }
    
    return Response(
        json.dumps(data, indent=2),
        mimetype='application/json',
        headers={'Content-Disposition': 'attachment; filename=oauth_clients.json'}
    )

@api_bp.route('/export/tokens', methods=['GET'])
def export_tokens():
    try:
        tokens = Token.query.all()
        token_list = []
        for t in tokens:
            try:
                token_list.append(t.to_dict(include_token=True))
            except Exception as e:
                current_app.logger.error(f'Error serializing token {t.id}: {e}')
                continue
        
        data = {
            'exported_at': utcnow().isoformat(),
            'version': '1.0',
            'tokens': token_list
        }
        
        return Response(
            json.dumps(data, indent=2),
            mimetype='application/json',
            headers={'Content-Disposition': 'attachment; filename=oauth_tokens.json'}
        )
    except Exception as e:
        current_app.logger.error(f'Error exporting tokens: {e}')
        return jsonify({
            'error': 'Export failed',
            'error_description': str(e)
        }), 500

@api_bp.route('/export/all', methods=['GET'])
def export_all():
    clients = Client.query.all()
    tokens = Token.query.all()
    scopes = Scope.query.all()
    auth_codes = AuthorizationCode.query.all()
    logs = Log.query.all()
    simulated_errors = SimulatedError.query.all()
    
    data = {
        'exported_at': utcnow().isoformat(),
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

@api_bp.route('/tokens/<int:token_id>', methods=['GET'])
def get_token_detail(token_id):
    token = Token.query.get_or_404(token_id)
    token_dict = token.to_dict(include_token=True)
    
    introspect_result = None
    if token.is_active():
        validated_token, error = validate_token(token.access_token)
        if validated_token:
            introspect_result = validated_token.to_introspect()
        else:
            introspect_result = {'active': False, 'error': error}
    else:
        introspect_result = {'active': False, 'error': 'Token is revoked or expired'}
    
    token_dict['introspect'] = introspect_result
    return jsonify(token_dict)

@api_bp.route('/import', methods=['POST'])
def import_data():
    data = None
    try:
        if 'file' in request.files:
            file = request.files['file']
            if not file or file.filename == '':
                return jsonify({
                    'success': False,
                    'error': 'No file uploaded',
                    'error_description': '请选择要导入的JSON文件'
                }), 400
            
            content = file.read()
            if not content or len(content.strip()) == 0:
                return jsonify({
                    'success': False,
                    'error': 'Empty file',
                    'error_description': '上传的文件是空的，请检查文件内容'
                }), 400
            
            try:
                data = json.loads(content.decode('utf-8'))
            except json.JSONDecodeError as e:
                return jsonify({
                    'success': False,
                    'error': 'Invalid JSON format',
                    'error_description': f'JSON格式错误: {str(e)}，请检查文件内容是否为有效的JSON格式'
                }), 400
        else:
            data = request.get_json()
            if not data:
                return jsonify({
                    'success': False,
                    'error': 'No data provided',
                    'error_description': '请提供要导入的JSON数据'
                }), 400
        
        if not isinstance(data, dict):
            return jsonify({
                'success': False,
                'error': 'Invalid data format',
                'error_description': '导入的数据必须是JSON对象格式'
            }), 400
        
        has_valid_data = any(key in data for key in ['clients', 'scopes', 'tokens', 'simulated_errors'])
        if not has_valid_data:
            return jsonify({
                'success': False,
                'error': 'No valid data sections found',
                'error_description': '未找到有效的数据段，请确保JSON包含clients、scopes、tokens或simulated_errors中的至少一个'
            }), 400
        
        if 'clients' in data and not isinstance(data['clients'], list):
            return jsonify({
                'success': False,
                'error': 'Invalid clients format',
                'error_description': 'clients字段必须是数组格式'
            }), 400
        
        if 'tokens' in data and not isinstance(data['tokens'], list):
            return jsonify({
                'success': False,
                'error': 'Invalid tokens format',
                'error_description': 'tokens字段必须是数组格式'
            }), 400
        
        if 'scopes' in data and not isinstance(data['scopes'], list):
            return jsonify({
                'success': False,
                'error': 'Invalid scopes format',
                'error_description': 'scopes字段必须是数组格式'
            }), 400
        
        if 'simulated_errors' in data and not isinstance(data['simulated_errors'], list):
            return jsonify({
                'success': False,
                'error': 'Invalid simulated_errors format',
                'error_description': 'simulated_errors字段必须是数组格式'
            }), 400
        
        results = {
            'clients': {'imported': 0, 'skipped': 0, 'errors': []},
            'scopes': {'imported': 0, 'skipped': 0, 'errors': []},
            'tokens': {'imported': 0, 'skipped': 0, 'errors': []},
            'simulated_errors': {'imported': 0, 'skipped': 0, 'errors': []}
        }
        
        mode = request.args.get('mode', 'skip')
        
        if 'clients' in data:
            for client_data in data['clients']:
                try:
                    existing = Client.query.filter_by(client_id=client_data.get('client_id')).first()
                    if existing:
                        if mode == 'skip':
                            results['clients']['skipped'] += 1
                            results['clients']['errors'].append(
                                f"Client {client_data.get('client_id')} ({client_data.get('name')}) already exists, skipped"
                            )
                            continue
                        elif mode == 'overwrite':
                            existing.name = client_data.get('name', existing.name)
                            existing.description = client_data.get('description', existing.description)
                            existing.redirect_uris = ','.join(client_data.get('redirect_uris', existing.get_redirect_uris()))
                            existing.grant_types = ','.join(client_data.get('grant_types', existing.get_grant_types()))
                            existing.token_format = client_data.get('token_format', existing.token_format)
                            existing.token_expire_seconds = client_data.get('token_expire_seconds', existing.token_expire_seconds)
                            existing.require_consent = client_data.get('require_consent', existing.require_consent)
                            existing.is_active = client_data.get('is_active', existing.is_active)
                            if 'client_secret' in client_data:
                                existing.client_secret = client_data['client_secret']
                            results['clients']['imported'] += 1
                            continue
                        else:
                            results['clients']['errors'].append(
                                f"Client {client_data.get('client_id')} ({client_data.get('name')}) already exists"
                            )
                            continue
                    
                    client = Client(
                        client_id=client_data.get('client_id'),
                        client_secret=client_data.get('client_secret'),
                        name=client_data['name'],
                        description=client_data.get('description', ''),
                        redirect_uris=','.join(client_data.get('redirect_uris', [])),
                        grant_types=','.join(client_data.get('grant_types', ['authorization_code', 'client_credentials'])),
                        token_format=client_data.get('token_format', 'jwt'),
                        token_expire_seconds=client_data.get('token_expire_seconds', 3600),
                        require_consent=client_data.get('require_consent', True),
                        is_active=client_data.get('is_active', True)
                    )
                    db.session.add(client)
                    results['clients']['imported'] += 1
                except Exception as e:
                    results['clients']['errors'].append(f"Error importing client {client_data.get('name')}: {str(e)}")
        
        db.session.flush()
        
        if 'scopes' in data:
            for scope_data in data['scopes']:
                try:
                    existing = Scope.query.filter_by(name=scope_data.get('name')).first()
                    if existing:
                        if mode == 'skip':
                            results['scopes']['skipped'] += 1
                            continue
                        elif mode == 'overwrite':
                            existing.description = scope_data.get('description', existing.description)
                            existing.is_enabled = scope_data.get('is_enabled', existing.is_enabled)
                            results['scopes']['imported'] += 1
                            continue
                        else:
                            results['scopes']['errors'].append(f"Scope {scope_data.get('name')} already exists")
                            continue
                    
                    scope = Scope(
                        name=scope_data['name'],
                        description=scope_data.get('description', ''),
                        is_enabled=scope_data.get('is_enabled', True)
                    )
                    db.session.add(scope)
                    results['scopes']['imported'] += 1
                except Exception as e:
                    results['scopes']['errors'].append(f"Error importing scope {scope_data.get('name')}: {str(e)}")
        
        db.session.flush()
        
        if 'tokens' in data:
            for token_data in data['tokens']:
                try:
                    existing = Token.query.filter_by(access_token=token_data.get('access_token')).first()
                    if existing:
                        if mode == 'skip':
                            results['tokens']['skipped'] += 1
                            continue
                        elif mode == 'overwrite':
                            existing.refresh_token = token_data.get('refresh_token', existing.refresh_token)
                            existing.is_revoked = token_data.get('is_revoked', existing.is_revoked)
                            results['tokens']['imported'] += 1
                            continue
                        else:
                            results['tokens']['errors'].append(f"Token {token_data.get('id')} already exists")
                            continue
                    
                    from datetime import datetime
                    expires_at = token_data.get('expires_at')
                    if isinstance(expires_at, str):
                        expires_at = datetime.fromisoformat(expires_at.replace('Z', '+00:00')).replace(tzinfo=None)
                    
                    created_at = token_data.get('created_at')
                    if isinstance(created_at, str):
                        created_at = datetime.fromisoformat(created_at.replace('Z', '+00:00')).replace(tzinfo=None)
                    
                    token = Token(
                        access_token=token_data['access_token'],
                        refresh_token=token_data.get('refresh_token'),
                        client_id=token_data['client_id'],
                        user_id=token_data.get('user_id'),
                        token_type=token_data.get('token_type', 'Bearer'),
                        scope=' '.join(token_data.get('scope', [])) if isinstance(token_data.get('scope'), list) else token_data.get('scope', ''),
                        expires_at=expires_at,
                        is_revoked=token_data.get('is_revoked', False),
                        grant_type=token_data.get('grant_type'),
                        token_format=token_data.get('token_format', 'jwt'),
                        created_at=created_at
                    )
                    db.session.add(token)
                    results['tokens']['imported'] += 1
                except Exception as e:
                    results['tokens']['errors'].append(f"Error importing token: {str(e)}")
        
        db.session.flush()
        
        if 'simulated_errors' in data:
            for error_data in data['simulated_errors']:
                try:
                    existing = SimulatedError.query.filter_by(name=error_data.get('name')).first()
                    if existing:
                        if mode == 'skip':
                            results['simulated_errors']['skipped'] += 1
                            continue
                        elif mode == 'overwrite':
                            existing.description = error_data.get('description', existing.description)
                            existing.error_type = error_data.get('error_type', existing.error_type)
                            existing.status_code = error_data.get('status_code', existing.status_code)
                            existing.error_message = error_data.get('error_message', existing.error_message)
                            existing.enabled = error_data.get('enabled', existing.enabled)
                            existing.affected_endpoints = ','.join(error_data.get('affected_endpoints', [])) if isinstance(error_data.get('affected_endpoints'), list) else error_data.get('affected_endpoints', '')
                            results['simulated_errors']['imported'] += 1
                            continue
                        else:
                            results['simulated_errors']['errors'].append(f"Simulated error {error_data.get('name')} already exists")
                            continue
                    
                    error = SimulatedError(
                        name=error_data['name'],
                        description=error_data.get('description', ''),
                        error_type=error_data['error_type'],
                        status_code=error_data.get('status_code', 400),
                        error_message=error_data.get('error_message', ''),
                        enabled=error_data.get('enabled', False),
                        affected_endpoints=','.join(error_data.get('affected_endpoints', [])) if isinstance(error_data.get('affected_endpoints'), list) else error_data.get('affected_endpoints', '')
                    )
                    db.session.add(error)
                    results['simulated_errors']['imported'] += 1
                except Exception as e:
                    results['simulated_errors']['errors'].append(f"Error importing simulated error {error_data.get('name')}: {str(e)}")
        
        db.session.commit()
        
        log_request(
            'data_import',
            success=True,
            error_message=f"Imported: clients={results['clients']['imported']}, scopes={results['scopes']['imported']}, tokens={results['tokens']['imported']}, errors={results['simulated_errors']['imported']}"
        )
        
        return jsonify({
            'success': True,
            'message': 'Import completed',
            'results': results
        })
        
    except Exception as e:
        db.session.rollback()
        log_request(
            'data_import',
            success=False,
            error_message=str(e)
        )
        return jsonify({'error': f'Import failed: {str(e)}'}), 500
