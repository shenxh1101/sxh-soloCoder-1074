import json
import base64
import urllib.parse
from flask import Blueprint, render_template, request, redirect, url_for, jsonify, session
from app import db
from app.models import Token, Client, SimulatedError, Scope, Log, AuthorizationCode, utcnow
from app.utils import log_request, create_token, validate_token

admin_bp = Blueprint('admin', __name__)

@admin_bp.route('/')
def index():
    tokens = Token.query.order_by(Token.created_at.desc()).all()
    active_tokens = [t for t in tokens if t.is_active()]
    clients = Client.query.order_by(Client.created_at.desc()).all()
    simulated_errors = SimulatedError.query.order_by(SimulatedError.id).all()
    client_names = {c.client_id: c.name for c in clients}
    
    return render_template('admin.html',
        tokens=tokens,
        active_tokens=active_tokens,
        clients=clients,
        simulated_errors=simulated_errors,
        client_names=client_names
    )

@admin_bp.route('/tokens')
def tokens():
    all_tokens = Token.query.order_by(Token.created_at.desc()).limit(200).all()
    clients = Client.query.all()
    client_map = {c.client_id: c.name for c in clients}
    
    filter_client = request.args.get('client_id', '')
    filter_status = request.args.get('status', 'all')
    
    tokens = all_tokens
    if filter_client:
        tokens = [t for t in tokens if t.client_id == filter_client]
    
    if filter_status == 'active':
        tokens = [t for t in tokens if t.is_active()]
    elif filter_status == 'revoked':
        tokens = [t for t in tokens if t.is_revoked]
    elif filter_status == 'expired':
        tokens = [t for t in tokens if t.is_expired() and not t.is_revoked]
    
    active_count = sum(1 for t in tokens if t.is_active())
    revoked_count = sum(1 for t in tokens if t.is_revoked)
    expired_count = sum(1 for t in tokens if t.is_expired() and not t.is_revoked)
    
    return render_template('admin_tokens.html',
        tokens=tokens,
        clients=clients,
        client_map=client_map,
        filter_client=filter_client,
        filter_status=filter_status,
        active_count=active_count,
        revoked_count=revoked_count,
        expired_count=expired_count
    )

@admin_bp.route('/tokens/<int:token_id>/revoke', methods=['POST'])
def revoke_token(token_id):
    token = Token.query.get_or_404(token_id)
    token.is_revoked = True
    db.session.commit()
    
    log_request(
        'admin_token_revoke',
        client_id=token.client_id,
        user_id=token.user_id,
        success=True
    )
    
    return redirect(url_for('admin.tokens'))

@admin_bp.route('/tokens/revoke-all', methods=['POST'])
def revoke_all_tokens():
    client_id = request.form.get('client_id')
    
    query = Token.query.filter_by(is_revoked=False)
    if client_id:
        query = query.filter_by(client_id=client_id)
    
    count = query.update({'is_revoked': True})
    db.session.commit()
    
    log_request(
        'admin_bulk_revoke',
        client_id=client_id,
        success=True,
        error_message=f'Revoked {count} tokens'
    )
    
    return redirect(url_for('admin.tokens'))

@admin_bp.route('/simulated-errors')
def simulated_errors():
    errors = SimulatedError.query.order_by(SimulatedError.id).all()
    return render_template('simulated_errors.html', errors=errors)

@admin_bp.route('/simulated-errors/<int:error_id>/toggle', methods=['POST'])
def toggle_simulated_error(error_id):
    error = SimulatedError.query.get_or_404(error_id)
    error.enabled = not error.enabled
    db.session.commit()
    return redirect(url_for('admin.simulated_errors'))

@admin_bp.route('/simulated-errors/new', methods=['GET', 'POST'])
def new_simulated_error():
    if request.method == 'POST':
        affected_endpoints = request.form.getlist('affected_endpoints')
        error = SimulatedError(
            name=request.form['name'],
            description=request.form.get('description', ''),
            error_type=request.form['error_type'],
            status_code=int(request.form.get('status_code', 400)),
            error_message=request.form.get('error_message', ''),
            enabled=request.form.get('enabled') == '1',
            affected_endpoints=','.join(affected_endpoints)
        )
        db.session.add(error)
        db.session.commit()
        return redirect(url_for('admin.simulated_errors'))
    
    error_types = [
        ('invalid_request', 'Invalid Request (400)'),
        ('invalid_client', 'Invalid Client (401)'),
        ('invalid_grant', 'Invalid Grant (400)'),
        ('unauthorized_client', 'Unauthorized Client (400)'),
        ('unsupported_grant_type', 'Unsupported Grant Type (400)'),
        ('invalid_scope', 'Invalid Scope (400)'),
        ('access_denied', 'Access Denied (403)'),
        ('invalid_token', 'Invalid Token (401)'),
        ('insufficient_scope', 'Insufficient Scope (403)'),
        ('server_error', 'Server Error (500)'),
        ('temporarily_unavailable', 'Temporarily Unavailable (503)')
    ]
    endpoint_options = [
        ('authorize', 'Authorize Endpoint (/oauth/authorize)'),
        ('token', 'Token Endpoint (/oauth/token)'),
        ('introspect', 'Introspect Endpoint (/oauth/introspect)'),
        ('revoke', 'Revoke Endpoint (/oauth/revoke)')
    ]
    return render_template('simulated_error_form.html', error=None, error_types=error_types, endpoint_options=endpoint_options)

@admin_bp.route('/simulated-errors/<int:error_id>/edit', methods=['GET', 'POST'])
def edit_simulated_error(error_id):
    error = SimulatedError.query.get_or_404(error_id)
    
    if request.method == 'POST':
        affected_endpoints = request.form.getlist('affected_endpoints')
        error.name = request.form['name']
        error.description = request.form.get('description', '')
        error.error_type = request.form['error_type']
        error.status_code = int(request.form.get('status_code', 400))
        error.error_message = request.form.get('error_message', '')
        error.enabled = request.form.get('enabled') == '1'
        error.affected_endpoints = ','.join(affected_endpoints)
        db.session.commit()
        return redirect(url_for('admin.simulated_errors'))
    
    error_types = [
        ('invalid_request', 'Invalid Request (400)'),
        ('invalid_client', 'Invalid Client (401)'),
        ('invalid_grant', 'Invalid Grant (400)'),
        ('unauthorized_client', 'Unauthorized Client (400)'),
        ('unsupported_grant_type', 'Unsupported Grant Type (400)'),
        ('invalid_scope', 'Invalid Scope (400)'),
        ('access_denied', 'Access Denied (403)'),
        ('invalid_token', 'Invalid Token (401)'),
        ('insufficient_scope', 'Insufficient Scope (403)'),
        ('server_error', 'Server Error (500)'),
        ('temporarily_unavailable', 'Temporarily Unavailable (503)')
    ]
    endpoint_options = [
        ('authorize', 'Authorize Endpoint (/oauth/authorize)'),
        ('token', 'Token Endpoint (/oauth/token)'),
        ('introspect', 'Introspect Endpoint (/oauth/introspect)'),
        ('revoke', 'Revoke Endpoint (/oauth/revoke)')
    ]
    return render_template('simulated_error_form.html', error=error, error_types=error_types, endpoint_options=endpoint_options)

@admin_bp.route('/simulated-errors/<int:error_id>/delete', methods=['POST'])
def delete_simulated_error(error_id):
    error = SimulatedError.query.get_or_404(error_id)
    db.session.delete(error)
    db.session.commit()
    return redirect(url_for('admin.simulated_errors'))

@admin_bp.route('/init-simulated-errors', methods=['POST'])
def init_simulated_errors():
    default_errors = [
        {
            'name': 'Token Expired',
            'description': 'Simulates an expired token scenario',
            'error_type': 'invalid_token',
            'status_code': 401,
            'error_message': 'The token has expired'
        },
        {
            'name': 'Invalid Token',
            'description': 'Simulates an invalid token scenario',
            'error_type': 'invalid_token',
            'status_code': 401,
            'error_message': 'The token is invalid'
        },
        {
            'name': 'Insufficient Scope',
            'description': 'Simulates insufficient scope for the requested resource',
            'error_type': 'insufficient_scope',
            'status_code': 403,
            'error_message': 'The token does not have the required scope'
        },
        {
            'name': 'Server Error',
            'description': 'Simulates an internal server error',
            'error_type': 'server_error',
            'status_code': 500,
            'error_message': 'An internal server error occurred'
        },
        {
            'name': 'Access Denied',
            'description': 'Simulates user denying access during authorization',
            'error_type': 'access_denied',
            'status_code': 403,
            'error_message': 'The user denied the authorization request'
        },
        {
            'name': 'Invalid Grant',
            'description': 'Simulates an invalid grant error during token exchange',
            'error_type': 'invalid_grant',
            'status_code': 400,
            'error_message': 'The authorization grant is invalid'
        },
        {
            'name': 'Invalid Client',
            'description': 'Simulates invalid client credentials',
            'error_type': 'invalid_client',
            'status_code': 401,
            'error_message': 'Client authentication failed'
        }
    ]
    
    for error_data in default_errors:
        if not SimulatedError.query.filter_by(name=error_data['name']).first():
            error = SimulatedError(**error_data)
            db.session.add(error)
    
    db.session.commit()
    return redirect(url_for('admin.simulated_errors'))

@admin_bp.route('/import', methods=['GET', 'POST'])
def import_page():
    if request.method == 'POST':
        mode = request.form.get('mode', 'skip')
        return redirect(url_for('api.import_data', mode=mode))
    
    return render_template('import.html')

@admin_bp.route('/playground', methods=['GET'])
def playground():
    clients = Client.query.filter_by(is_active=True).all()
    scopes = Scope.query.filter_by(is_enabled=True).all()
    return render_template('playground.html', clients=clients, scopes=scopes)

@admin_bp.route('/playground/run-client-credentials', methods=['POST'])
def run_client_credentials():
    data = request.get_json()
    client_id = data.get('client_id')
    client_secret = data.get('client_secret')
    scope = data.get('scope', '')
    token_format = data.get('token_format', 'jwt')
    
    steps = []
    
    client = Client.query.filter_by(
        client_id=client_id,
        client_secret=client_secret,
        is_active=True
    ).first()
    
    if not client:
        steps.append({
            'name': 'Client Authentication',
            'status': 'error',
            'request': f'POST /oauth/token\nAuthorization: Basic {base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()}\nContent-Type: application/x-www-form-urlencoded\n\ngrant_type=client_credentials&scope={scope}',
            'response': 'HTTP/1.1 401 Unauthorized\n\n{"error": "invalid_client", "error_description": "Invalid client credentials"}',
            'status_code': 401
        })
        return jsonify({'success': False, 'steps': steps})
    
    if token_format != client.token_format:
        client.token_format = token_format
        db.session.commit()
    
    auth_header = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()
    
    steps.append({
        'name': '1. Client Authentication',
        'status': 'success',
        'request': f'POST /oauth/token\nAuthorization: Basic {auth_header}\nContent-Type: application/x-www-form-urlencoded\n\ngrant_type=client_credentials&scope={scope}',
        'response': None,
        'status_code': None
    })
    
    from datetime import timedelta
    token_data = create_token(client, None, scope, 'client_credentials')
    
    steps[-1]['response'] = f'HTTP/1.1 200 OK\nContent-Type: application/json\n\n{json.dumps(token_data, indent=2)}'
    steps[-1]['status_code'] = 200
    
    steps.append({
        'name': '2. Token Introspection',
        'status': 'success',
        'request': f'POST /oauth/introspect\nAuthorization: Basic {auth_header}\nContent-Type: application/x-www-form-urlencoded\n\ntoken={token_data["access_token"]}',
        'response': None,
        'status_code': None
    })
    
    validated_token, error = validate_token(token_data['access_token'])
    if validated_token:
        intro_result = validated_token.to_introspect()
    else:
        intro_result = {'active': False, 'error': error}
    
    steps[-1]['response'] = f'HTTP/1.1 200 OK\nContent-Type: application/json\n\n{json.dumps(intro_result, indent=2)}'
    steps[-1]['status_code'] = 200
    
    return jsonify({
        'success': True,
        'steps': steps,
        'access_token': token_data['access_token'],
        'refresh_token': token_data.get('refresh_token'),
        'token_type': token_data['token_type'],
        'expires_in': token_data['expires_in']
    })

@admin_bp.route('/playground/run-authorization-code', methods=['POST'])
def run_authorization_code():
    data = request.get_json()
    client_id = data.get('client_id')
    client_secret = data.get('client_secret')
    redirect_uri = data.get('redirect_uri', 'http://localhost:3000/callback')
    scope = data.get('scope', '')
    user_id = data.get('user_id', 'test_user')
    token_format = data.get('token_format', 'jwt')
    
    steps = []
    
    client = Client.query.filter_by(
        client_id=client_id,
        client_secret=client_secret,
        is_active=True
    ).first()
    
    if not client:
        steps.append({
            'name': 'Client Authentication',
            'status': 'error',
            'request': f'GET /oauth/authorize?client_id={client_id}&response_type=code&redirect_uri={redirect_uri}&scope={scope}',
            'response': 'HTTP/1.1 400 Bad Request\n\n{"error": "invalid_client", "error_description": "Unknown client"}',
            'status_code': 401
        })
        return jsonify({'success': False, 'steps': steps})
    
    if token_format != client.token_format:
        client.token_format = token_format
        db.session.commit()
    
    auth_header = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()
    
    steps.append({
        'name': '1. Authorization Request',
        'status': 'success',
        'request': f'GET /oauth/authorize\n\n?client_id={client_id}\n&response_type=code\n&redirect_uri={urllib.parse.quote(redirect_uri)}\n&scope={urllib.parse.quote(scope)}',
        'response': f'HTTP/1.1 302 Found\nLocation: /login?next=%2Foauth%2Fauthorize%3Fclient_id%3D{client_id}%26response_type%3Dcode%26redirect_uri%3D{urllib.parse.quote(redirect_uri)}%26scope%3D{urllib.parse.quote(scope)}',
        'status_code': 302
    })
    
    steps.append({
        'name': '2. User Login & Consent',
        'status': 'success',
        'request': f'POST /login\n\nusername={user_id}&password=any_password',
        'response': f'HTTP/1.1 302 Found\nLocation: /oauth/authorize?client_id={client_id}&response_type=code&redirect_uri={urllib.parse.quote(redirect_uri)}&scope={urllib.parse.quote(scope)}&consent_given=1',
        'status_code': 302
    })
    
    from datetime import timedelta, timezone
    auth_code = AuthorizationCode(
        client_id=client.client_id,
        user_id=user_id,
        redirect_uri=redirect_uri,
        scope=scope,
        expires_at=utcnow() + timedelta(seconds=60)
    )
    db.session.add(auth_code)
    db.session.commit()
    
    steps.append({
        'name': '3. Authorization Code Redirect',
        'status': 'success',
        'request': None,
        'response': f'HTTP/1.1 302 Found\nLocation: {redirect_uri}?code={auth_code.code}',
        'status_code': 302,
        'code': auth_code.code
    })
    
    steps.append({
        'name': '4. Token Exchange',
        'status': 'success',
        'request': f'POST /oauth/token\nAuthorization: Basic {auth_header}\nContent-Type: application/x-www-form-urlencoded\n\ngrant_type=authorization_code&code={auth_code.code}&redirect_uri={urllib.parse.quote(redirect_uri)}',
        'response': None,
        'status_code': None
    })
    
    token_data = create_token(client, user_id, scope, 'authorization_code')
    auth_code.is_used = True
    db.session.commit()
    
    steps[-1]['response'] = f'HTTP/1.1 200 OK\nContent-Type: application/json\n\n{json.dumps(token_data, indent=2)}'
    steps[-1]['status_code'] = 200
    
    steps.append({
        'name': '5. Token Introspection',
        'status': 'success',
        'request': f'POST /oauth/introspect\nAuthorization: Basic {auth_header}\nContent-Type: application/x-www-form-urlencoded\n\ntoken={token_data["access_token"]}',
        'response': None,
        'status_code': None
    })
    
    validated_token, error = validate_token(token_data['access_token'])
    if validated_token:
        intro_result = validated_token.to_introspect()
    else:
        intro_result = {'active': False, 'error': error}
    
    steps[-1]['response'] = f'HTTP/1.1 200 OK\nContent-Type: application/json\n\n{json.dumps(intro_result, indent=2)}'
    steps[-1]['status_code'] = 200
    
    return jsonify({
        'success': True,
        'steps': steps,
        'authorization_code': auth_code.code,
        'access_token': token_data['access_token'],
        'refresh_token': token_data.get('refresh_token'),
        'token_type': token_data['token_type'],
        'expires_in': token_data['expires_in']
    })
