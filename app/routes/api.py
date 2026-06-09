import json
from datetime import datetime
from flask import Blueprint, request, jsonify, Response, current_app, session
from app import db
from app.models import Client, Scope, Token, Log, AuthorizationCode, SimulatedError, ImportHistory, ErrorHit, utcnow
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

@api_bp.route('/import/preview', methods=['POST'])
def preview_import():
    data = None
    filename = None
    try:
        if 'file' in request.files:
            file = request.files['file']
            if not file or file.filename == '':
                return jsonify({
                    'success': False,
                    'error': 'No file uploaded',
                    'error_description': 'Please select the JSON file to import'
                }), 400
            
            filename = file.filename
            content = file.read()
            if not content or len(content.strip()) == 0:
                return jsonify({
                    'success': False,
                    'error': 'Empty file',
                    'error_description': 'The uploaded file is empty, please check the file content'
                }), 400
            
            try:
                data = json.loads(content.decode('utf-8'))
            except json.JSONDecodeError as e:
                return jsonify({
                    'success': False,
                    'error': 'Invalid JSON format',
                    'error_description': f'JSON format error: {str(e)}, please check if the file content is valid JSON format'
                }), 400
        else:
            data = request.get_json()
            if not data:
                return jsonify({
                    'success': False,
                    'error': 'No data provided',
                    'error_description': 'Please provide the JSON data to import'
                }), 400
        
        if not isinstance(data, dict):
            return jsonify({
                'success': False,
                'error': 'Invalid data format',
                'error_description': 'The imported data must be a JSON object format'
            }), 400
        
        has_valid_data = any(key in data for key in ['clients', 'scopes', 'tokens', 'simulated_errors'])
        if not has_valid_data:
            return jsonify({
                'success': False,
                'error': 'No valid data sections found',
                'error_description': 'No valid data sections found, please ensure JSON contains at least one of clients, scopes, tokens, or simulated_errors'
            }), 400
        
        for key in ['clients', 'scopes', 'tokens', 'simulated_errors']:
            if key in data and not isinstance(data[key], list):
                return jsonify({
                    'success': False,
                    'error': f'Invalid {key} format',
                    'error_description': f'{key} field must be an array format'
                }), 400
        
        mode = request.args.get('mode', 'skip')
        existing_clients = {c.client_id: c for c in Client.query.all()}
        existing_tokens = {t.access_token: t for t in Token.query.all()}
        existing_scopes = {s.name: s for s in Scope.query.all()}
        existing_errors = {e.name: e for e in SimulatedError.query.all()}
        
        preview = {
            'summary': {
                'clients': {'new': 0, 'overwrite': 0, 'skip': 0, 'error': 0},
                'scopes': {'new': 0, 'overwrite': 0, 'skip': 0, 'error': 0},
                'tokens': {'new': 0, 'overwrite': 0, 'skip': 0, 'error': 0},
                'simulated_errors': {'new': 0, 'overwrite': 0, 'skip': 0, 'error': 0}
            },
            'details': {
                'clients': [],
                'scopes': [],
                'tokens': [],
                'simulated_errors': []
            },
            'warnings': [],
            'can_import': True
        }
        
        if 'clients' in data:
            for idx, client_data in enumerate(data['clients']):
                item = {'index': idx, 'data': client_data, 'action': None, 'reason': None}
                required_fields = ['client_id', 'name', 'redirect_uris']
                missing = [f for f in required_fields if f not in client_data or not client_data[f]]
                if missing:
                    item['action'] = 'error'
                    item['reason'] = f'Missing required fields: {", ".join(missing)}'
                    preview['summary']['clients']['error'] += 1
                    preview['can_import'] = False
                else:
                    existing = existing_clients.get(client_data['client_id'])
                    if existing:
                        if mode == 'skip':
                            item['action'] = 'skip'
                            item['reason'] = f'client_id already exists: {client_data["client_id"]}'
                            preview['summary']['clients']['skip'] += 1
                        elif mode == 'overwrite':
                            item['action'] = 'overwrite'
                            item['reason'] = f'Will overwrite existing client: {existing.name}'
                            preview['summary']['clients']['overwrite'] += 1
                    else:
                        item['action'] = 'new'
                        item['reason'] = 'New client'
                        preview['summary']['clients']['new'] += 1
                preview['details']['clients'].append(item)
        
        if 'scopes' in data:
            for idx, scope_data in enumerate(data['scopes']):
                item = {'index': idx, 'data': scope_data, 'action': None, 'reason': None}
                if 'name' not in scope_data or not scope_data['name']:
                    item['action'] = 'error'
                    item['reason'] = 'Missing required field: name'
                    preview['summary']['scopes']['error'] += 1
                    preview['can_import'] = False
                else:
                    existing = existing_scopes.get(scope_data['name'])
                    if existing:
                        if mode == 'skip':
                            item['action'] = 'skip'
                            item['reason'] = f'scope already exists: {scope_data["name"]}'
                            preview['summary']['scopes']['skip'] += 1
                        elif mode == 'overwrite':
                            item['action'] = 'overwrite'
                            item['reason'] = f'Will overwrite existing scope: {existing.name}'
                            preview['summary']['scopes']['overwrite'] += 1
                    else:
                        item['action'] = 'new'
                        item['reason'] = 'New scope'
                        preview['summary']['scopes']['new'] += 1
                preview['details']['scopes'].append(item)
        
        if 'tokens' in data:
            for idx, token_data in enumerate(data['tokens']):
                item = {'index': idx, 'data': {}, 'action': None, 'reason': None}
                token_display = {k: v for k, v in token_data.items() if k != 'access_token' and k != 'refresh_token'}
                if 'access_token' in token_data:
                    token_display['access_token'] = token_data['access_token'][:20] + '...'
                item['data'] = token_display
                
                required_fields = ['access_token', 'client_id', 'expires_at']
                missing = [f for f in required_fields if f not in token_data or not token_data[f]]
                if missing:
                    item['action'] = 'error'
                    item['reason'] = f'Missing required fields: {", ".join(missing)}'
                    preview['summary']['tokens']['error'] += 1
                    preview['can_import'] = False
                else:
                    if token_data['client_id'] not in existing_clients:
                        client_in_import = any(
                            c.get('client_id') == token_data['client_id'] 
                            for c in data.get('clients', [])
                        )
                        if not client_in_import:
                            item['action'] = 'error'
                            item['reason'] = f'Token references a non-existent client_id: {token_data["client_id"]}, which does not exist in existing clients or the import list'
                            preview['summary']['tokens']['error'] += 1
                            preview['can_import'] = False
                            preview['details']['tokens'].append(item)
                            continue
                    
                    existing = existing_tokens.get(token_data['access_token'])
                    if existing:
                        if mode == 'skip':
                            item['action'] = 'skip'
                            item['reason'] = 'access_token already exists'
                            preview['summary']['tokens']['skip'] += 1
                        elif mode == 'overwrite':
                            item['action'] = 'overwrite'
                            item['reason'] = 'Will overwrite existing token'
                            preview['summary']['tokens']['overwrite'] += 1
                    else:
                        item['action'] = 'new'
                        item['reason'] = 'New token'
                        preview['summary']['tokens']['new'] += 1
                preview['details']['tokens'].append(item)
        
        if 'simulated_errors' in data:
            for idx, error_data in enumerate(data['simulated_errors']):
                item = {'index': idx, 'data': error_data, 'action': None, 'reason': None}
                required_fields = ['name', 'error_type']
                missing = [f for f in required_fields if f not in error_data or not error_data[f]]
                if missing:
                    item['action'] = 'error'
                    item['reason'] = f'Missing required fields: {", ".join(missing)}'
                    preview['summary']['simulated_errors']['error'] += 1
                    preview['can_import'] = False
                else:
                    existing = existing_errors.get(error_data['name'])
                    if existing:
                        if mode == 'skip':
                            item['action'] = 'skip'
                            item['reason'] = f'Error config already exists: {error_data["name"]}'
                            preview['summary']['simulated_errors']['skip'] += 1
                        elif mode == 'overwrite':
                            item['action'] = 'overwrite'
                            item['reason'] = f'Will overwrite existing error config: {existing.name}'
                            preview['summary']['simulated_errors']['overwrite'] += 1
                    else:
                        item['action'] = 'new'
                        item['reason'] = 'New error config'
                        preview['summary']['simulated_errors']['new'] += 1
                preview['details']['simulated_errors'].append(item)
        
        preview_id = f"preview_{datetime.now().timestamp()}"
        session['import_preview'] = {
            'id': preview_id,
            'data': data,
            'mode': mode,
            'filename': filename,
            'preview': preview
        }
        
        return jsonify({
            'success': True,
            'preview_id': preview_id,
            'mode': mode,
            'filename': filename,
            'preview': preview
        })
        
    except Exception as e:
        current_app.logger.error(f'Import preview error: {e}')
        return jsonify({
            'success': False,
            'error': 'Preview failed',
            'error_description': str(e)
        }), 500

@api_bp.route('/import', methods=['POST'])
def import_data():
    data = None
    filename = None
    mode = request.args.get('mode', 'skip')
    atomic = request.args.get('atomic', 'true').lower() == 'true'
    confirm = request.args.get('confirm', 'false').lower() == 'true'
    preview_id = request.args.get('preview_id')
    
    import_history = ImportHistory(
        import_mode=mode,
        status='pending',
        source='pending',
        results='{}'
    )
    db.session.add(import_history)
    db.session.flush()
    
    try:
        if not confirm:
            raise Exception('Import not confirmed: Please preview and confirm the import first')
        
        import_history.source = filename or 'direct_input'
        db.session.flush()
        
        if preview_id and 'import_preview' in session and session['import_preview']['id'] == preview_id:
            preview_data = session['import_preview']
            data = preview_data['data']
            mode = preview_data['mode']
            filename = preview_data['filename']
            import_history.source = filename or 'direct_input'
            import_history.import_mode = mode
            db.session.flush()
            del session['import_preview']
        else:
            if 'file' in request.files:
                file = request.files['file']
                if not file or file.filename == '':
                    raise Exception('No file uploaded: Please select the JSON file to import')
                
                filename = file.filename
                import_history.source = filename
                db.session.flush()
                
                content = file.read()
                if not content or len(content.strip()) == 0:
                    raise Exception('Empty file: The uploaded file is empty, please check the file content')
                
                try:
                    data = json.loads(content.decode('utf-8'))
                except json.JSONDecodeError as e:
                    raise Exception(f'Invalid JSON format: JSON format error: {str(e)}, please check if the file content is valid JSON format')
            else:
                data = request.get_json()
                if not data:
                    raise Exception('No data provided: Please provide the JSON data to import')
            
            if not isinstance(data, dict):
                raise Exception('Invalid data format: The imported data must be a JSON object format')
        
        results = {
            'clients': {'imported': 0, 'skipped': 0, 'errors': [], 'details': []},
            'scopes': {'imported': 0, 'skipped': 0, 'errors': [], 'details': []},
            'tokens': {'imported': 0, 'skipped': 0, 'errors': [], 'details': []},
            'simulated_errors': {'imported': 0, 'skipped': 0, 'errors': [], 'details': []}
        }
        
        has_errors = False
        
        if 'clients' in data:
            for client_data in data['clients']:
                try:
                    existing = Client.query.filter_by(client_id=client_data.get('client_id')).first()
                    if existing:
                        if mode == 'skip':
                            results['clients']['skipped'] += 1
                            results['clients']['details'].append({
                                'client_id': client_data.get('client_id'),
                                'name': client_data.get('name'),
                                'action': 'skipped',
                                'reason': 'already_exists'
                            })
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
                            results['clients']['details'].append({
                                'client_id': client_data.get('client_id'),
                                'name': client_data.get('name'),
                                'action': 'overwritten'
                            })
                            continue
                        else:
                            results['clients']['errors'].append(
                                f"Client {client_data.get('client_id')} ({client_data.get('name')}) already exists"
                            )
                            has_errors = True
                            continue
                    
                    client = Client(
                        client_id=client_data.get('client_id'),
                        client_secret=client_data.get('client_secret') if 'client_secret' in client_data else None,
                        name=client_data['name'],
                        description=client_data.get('description', ''),
                        redirect_uris=','.join(client_data['redirect_uris']),
                        grant_types=','.join(client_data.get('grant_types', ['authorization_code', 'client_credentials'])),
                        token_format=client_data.get('token_format', 'jwt'),
                        token_expire_seconds=client_data.get('token_expire_seconds', 3600),
                        require_consent=client_data.get('require_consent', True),
                        is_active=client_data.get('is_active', True)
                    )
                    db.session.add(client)
                    results['clients']['imported'] += 1
                    results['clients']['details'].append({
                        'client_id': client_data.get('client_id'),
                        'name': client_data.get('name'),
                        'action': 'created'
                    })
                except Exception as e:
                    results['clients']['errors'].append(f"Error importing client {client_data.get('client_id')}: {str(e)}")
                    has_errors = True
        
        db.session.flush()
        
        if has_errors and atomic:
            raise Exception(f"Import failed, found {len(results['clients']['errors'])} errors, all changes have been rolled back")
        
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
                            has_errors = True
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
                    has_errors = True
        
        db.session.flush()
        
        if has_errors and atomic:
            raise Exception(f"Import failed, found {len(results['scopes']['errors'])} errors, all changes have been rolled back")
        
        if 'tokens' in data:
            existing_clients = {c.client_id: c for c in Client.query.all()}
            import_client_ids = {c.get('client_id') for c in data.get('clients', [])}
            
            for token_data in data['tokens']:
                try:
                    token_client_id = token_data.get('client_id')
                    if token_client_id not in existing_clients and token_client_id not in import_client_ids:
                        error_msg = f"Token references non-existent client_id: {token_client_id}, which does not exist in existing clients or the import list"
                        if atomic:
                            raise Exception(error_msg)
                        else:
                            results['tokens']['errors'].append(error_msg)
                            has_errors = True
                            continue
                    
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
                            has_errors = True
                            continue
                    
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
                    has_errors = True
        
        db.session.flush()
        
        if has_errors and atomic:
            raise Exception(f"Import failed, found {len(results['tokens']['errors'])} errors, all changes have been rolled back")
        
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
                            has_errors = True
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
                    has_errors = True
        
        if has_errors and atomic:
            raise Exception(f"Import failed, found {len(results['simulated_errors']['errors'])} errors, all changes have been rolled back")
        
        db.session.commit()
        
        if import_history:
            import_history.status = 'completed' if not has_errors else 'completed_with_errors'
            import_history.set_results(results)
            db.session.commit()
        
        log_request(
            'data_import',
            success=True,
            error_message=f"Imported: clients={results['clients']['imported']}, scopes={results['scopes']['imported']}, tokens={results['tokens']['imported']}, errors={results['simulated_errors']['imported']}"
        )
        
        return jsonify({
            'success': True,
            'message': 'Import completed',
            'import_id': import_history.id if import_history else None,
            'results': results,
            'has_errors': has_errors
        })
        
    except Exception as e:
        db.session.rollback()
        if import_history:
            import_history.status = 'failed'
            import_history.error_message = str(e)
            db.session.commit()
        
        log_request(
            'data_import',
            success=False,
            error_message=str(e)
        )
        return jsonify({
            'success': False,
            'error': 'Import failed',
            'error_description': str(e),
            'import_id': import_history.id if import_history else None
        }), 500

@api_bp.route('/import/history', methods=['GET'])
def get_import_history():
    try:
        page = int(request.args.get('page', 1))
        per_page = int(request.args.get('per_page', 20))
        status = request.args.get('status')
        
        query = ImportHistory.query.order_by(ImportHistory.created_at.desc())
        
        if status:
            query = query.filter_by(status=status)
        
        pagination = query.paginate(page=page, per_page=per_page, error_out=False)
        
        return jsonify({
            'success': True,
            'data': [h.to_dict() for h in pagination.items],
            'pagination': {
                'page': page,
                'per_page': per_page,
                'total': pagination.total,
                'pages': pagination.pages,
                'has_next': pagination.has_next,
                'has_prev': pagination.has_prev
            }
        })
    except Exception as e:
        current_app.logger.error(f'Get import history error: {e}')
        return jsonify({
            'success': False,
            'error': 'Failed to get import history',
            'error_description': str(e)
        }), 500

@api_bp.route('/import/history/<int:import_id>', methods=['GET'])
def get_import_history_detail(import_id):
    try:
        history = ImportHistory.query.get_or_404(import_id)
        return jsonify({
            'success': True,
            'data': history.to_dict()
        })
    except Exception as e:
        current_app.logger.error(f'Get import history detail error: {e}')
        return jsonify({
            'success': False,
            'error': 'Failed to get import history detail',
            'error_description': str(e)
        }), 500

@api_bp.route('/import/history/<int:import_id>/report', methods=['GET'])
def download_import_report(import_id):
    try:
        history = ImportHistory.query.get_or_404(import_id)
        
        report = {
            'report_type': 'import_report',
            'generated_at': utcnow().isoformat(),
            'import_id': history.id,
            'import_mode': history.import_mode,
            'status': history.status,
            'source': history.source,
            'created_at': history.created_at.isoformat(),
            'results': history.get_results(),
            'error_message': history.error_message
        }
        
        filename = f'import_report_{history.id}_{history.created_at.strftime("%Y%m%d_%H%M%S")}.json'
        
        return Response(
            json.dumps(report, indent=2, ensure_ascii=False),
            mimetype='application/json',
            headers={'Content-Disposition': f'attachment; filename={filename}'}
        )
    except Exception as e:
        current_app.logger.error(f'Download import report error: {e}')
        return jsonify({
            'success': False,
            'error': 'Failed to download import report',
            'error_description': str(e)
        }), 500

@api_bp.route('/error-hits', methods=['GET'])
def get_error_hits():
    try:
        endpoint = request.args.get('endpoint')
        client_id = request.args.get('client_id')
        simulated_error_id = request.args.get('simulated_error_id')
        limit = int(request.args.get('limit', 100))
        
        query = ErrorHit.query.order_by(ErrorHit.created_at.desc())
        
        if endpoint:
            query = query.filter_by(endpoint=endpoint)
        if client_id:
            query = query.filter_by(client_id=client_id)
        if simulated_error_id:
            query = query.filter_by(simulated_error_id=int(simulated_error_id))
        
        hits = query.limit(limit).all()
        
        return jsonify({
            'success': True,
            'data': [h.to_dict() for h in hits],
            'count': len(hits)
        })
    except Exception as e:
        current_app.logger.error(f'Get error hits error: {e}')
        return jsonify({
            'success': False,
            'error': 'Failed to get error hits',
            'error_description': str(e)
        }), 500
