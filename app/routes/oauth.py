import json
from datetime import timedelta, timezone
from urllib.parse import urlencode, urlparse, parse_qs, urlunparse
from flask import Blueprint, request, redirect, render_template, jsonify, make_response, current_app
from app import db
from app.models import Client, AuthorizationCode, Token, utcnow
from app.utils import log_request, require_basic_auth, create_token, check_simulated_error, validate_token

oauth_bp = Blueprint('oauth', __name__)

@oauth_bp.route('/authorize', methods=['GET'])
def authorize():
    sim_error = check_simulated_error('invalid_request')
    if sim_error:
        log_request('authorize_error', success=False, error_message=sim_error[0]['error_description'])
        return jsonify(sim_error[0]), sim_error[1]
    
    response_type = request.args.get('response_type')
    client_id = request.args.get('client_id')
    redirect_uri = request.args.get('redirect_uri')
    scope = request.args.get('scope', '')
    state = request.args.get('state', '')
    
    client = Client.query.filter_by(client_id=client_id, is_active=True).first()
    
    if not client:
        log_request('authorize_error', client_id=client_id, success=False, error_message='Invalid client')
        return jsonify({'error': 'invalid_client', 'error_description': 'Unknown client'}), 400
    
    if response_type not in ['code']:
        log_request('authorize_error', client_id=client_id, success=False, error_message='Unsupported response type')
        return redirect_with_error(redirect_uri, 'unsupported_response_type', 'Response type not supported', state)
    
    valid_uris = client.get_redirect_uris()
    if redirect_uri not in valid_uris:
        log_request('authorize_error', client_id=client_id, success=False, error_message='Invalid redirect URI')
        return jsonify({'error': 'invalid_redirect_uri', 'error_description': 'Invalid redirect URI'}), 400
    
    if 'authorization_code' not in client.get_grant_types():
        log_request('authorize_error', client_id=client_id, success=False, error_message='Grant type not allowed')
        return redirect_with_error(redirect_uri, 'unauthorized_client', 'Authorization code grant not allowed', state)
    
    scopes = scope.split() if scope else []
    valid_scopes = [s.name for s in db.session.query(__import__('app.models').models.Scope).filter_by(is_enabled=True).all()]
    invalid_scopes = [s for s in scopes if s not in valid_scopes]
    if invalid_scopes:
        log_request('authorize_error', client_id=client_id, scope=scope, success=False, error_message=f'Invalid scope: {invalid_scopes}')
        return redirect_with_error(redirect_uri, 'invalid_scope', f'Invalid scope: {", ".join(invalid_scopes)}', state)
    
    session_id = request.cookies.get('oauth_session')
    user_id = None
    
    if session_id:
        from flask import session
        user_id = session.get(f'user_{session_id}')
    
    if not user_id:
        return redirect(f'/login?{urlencode({"next": request.full_path})}')
    
    if client.require_consent and not request.args.get('consent_given'):
        return render_template('authorize.html',
            client=client,
            redirect_uri=redirect_uri,
            scope=scope,
            state=state,
            response_type=response_type,
            scopes=scopes,
            user_id=user_id
        )
    
    sim_error = check_simulated_error('access_denied')
    if sim_error:
        log_request('authorize_error', client_id=client_id, user_id=user_id, success=False, error_message=sim_error[0]['error_description'])
        return redirect_with_error(redirect_uri, 'access_denied', sim_error[0]['error_description'], state)
    
    auth_code = AuthorizationCode(
        client_id=client.client_id,
        user_id=user_id,
        redirect_uri=redirect_uri,
        scope=scope,
        expires_at=utcnow() + timedelta(seconds=current_app.config['AUTH_CODE_EXPIRE_SECONDS'])
    )
    
    db.session.add(auth_code)
    db.session.commit()
    
    log_request(
        'authorize_success',
        client_id=client_id,
        user_id=user_id,
        scope=scope,
        success=True
    )
    
    params = {'code': auth_code.code}
    if state:
        params['state'] = state
    
    return redirect(f'{redirect_uri}?{urlencode(params)}')

@oauth_bp.route('/authorize', methods=['POST'])
def authorize_post():
    action = request.form.get('action')
    client_id = request.form.get('client_id')
    redirect_uri = request.form.get('redirect_uri')
    scope = request.form.get('scope', '')
    state = request.form.get('state', '')
    response_type = request.form.get('response_type')
    
    client = Client.query.filter_by(client_id=client_id, is_active=True).first()
    if not client:
        return jsonify({'error': 'invalid_client', 'error_description': 'Unknown client'}), 400
    
    if action == 'deny':
        log_request('authorize_denied', client_id=client_id, success=False, error_message='User denied access')
        return redirect_with_error(redirect_uri, 'access_denied', 'User denied access', state)
    
    return redirect(f'/oauth/authorize?{urlencode({
        "response_type": response_type,
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "scope": scope,
        "state": state,
        "consent_given": "1"
    })}')

@oauth_bp.route('/token', methods=['POST'])
@require_basic_auth
def token():
    sim_error = check_simulated_error('invalid_client')
    if sim_error:
        log_request('token_error', client_id=request.client.client_id, success=False, error_message=sim_error[0]['error_description'])
        return jsonify(sim_error[0]), sim_error[1]
    
    client = request.client
    grant_type = request.form.get('grant_type')
    
    if grant_type not in client.get_grant_types():
        log_request('token_error', client_id=client.client_id, grant_type=grant_type, success=False, error_message='Unsupported grant type')
        return jsonify({
            'error': 'unsupported_grant_type',
            'error_description': 'Grant type not supported for this client'
        }), 400
    
    if grant_type == 'client_credentials':
        scope = request.form.get('scope', '')
        scopes = scope.split() if scope else []
        valid_scopes = [s.name for s in db.session.query(__import__('app.models').models.Scope).filter_by(is_enabled=True).all()]
        invalid_scopes = [s for s in scopes if s not in valid_scopes]
        if invalid_scopes:
            log_request('token_error', client_id=client.client_id, grant_type=grant_type, scope=scope, success=False, error_message=f'Invalid scope: {invalid_scopes}')
            return jsonify({
                'error': 'invalid_scope',
                'error_description': f'Invalid scope: {", ".join(invalid_scopes)}'
            }), 400
        
        sim_error = check_simulated_error('invalid_grant')
        if sim_error:
            log_request('token_error', client_id=client.client_id, grant_type=grant_type, success=False, error_message=sim_error[0]['error_description'])
            return jsonify(sim_error[0]), sim_error[1]
        
        token_data = create_token(client, None, scope, 'client_credentials')
        
        log_request(
            'token_success',
            client_id=client.client_id,
            grant_type=grant_type,
            scope=scope,
            success=True
        )
        
        return jsonify(token_data)
    
    elif grant_type == 'authorization_code':
        code = request.form.get('code')
        redirect_uri = request.form.get('redirect_uri')
        
        if not code:
            log_request('token_error', client_id=client.client_id, grant_type=grant_type, success=False, error_message='Missing authorization code')
            return jsonify({
                'error': 'invalid_request',
                'error_description': 'Missing authorization code'
            }), 400
        
        auth_code = AuthorizationCode.query.filter_by(
            code=code,
            client_id=client.client_id,
            redirect_uri=redirect_uri,
            is_used=False
        ).first()
        
        if not auth_code:
            log_request('token_error', client_id=client.client_id, grant_type=grant_type, success=False, error_message='Invalid authorization code')
            return jsonify({
                'error': 'invalid_grant',
                'error_description': 'Invalid or expired authorization code'
            }), 400
        
        if auth_code.is_expired():
            log_request('token_error', client_id=client.client_id, grant_type=grant_type, success=False, error_message='Expired authorization code')
            return jsonify({
                'error': 'invalid_grant',
                'error_description': 'Authorization code has expired'
            }), 400
        
        sim_error = check_simulated_error('invalid_grant')
        if sim_error:
            log_request('token_error', client_id=client.client_id, grant_type=grant_type, success=False, error_message=sim_error[0]['error_description'])
            return jsonify(sim_error[0]), sim_error[1]
        
        auth_code.is_used = True
        db.session.commit()
        
        token_data = create_token(client, auth_code.user_id, auth_code.scope, 'authorization_code')
        
        log_request(
            'token_success',
            client_id=client.client_id,
            user_id=auth_code.user_id,
            grant_type=grant_type,
            scope=auth_code.scope,
            success=True
        )
        
        return jsonify(token_data)
    
    elif grant_type == 'refresh_token':
        refresh_token = request.form.get('refresh_token')
        
        if not refresh_token:
            log_request('token_error', client_id=client.client_id, grant_type=grant_type, success=False, error_message='Missing refresh token')
            return jsonify({
                'error': 'invalid_request',
                'error_description': 'Missing refresh token'
            }), 400
        
        token = Token.query.filter_by(
            refresh_token=refresh_token,
            client_id=client.client_id,
            is_revoked=False
        ).first()
        
        if not token or token.is_expired():
            log_request('token_error', client_id=client.client_id, grant_type=grant_type, success=False, error_message='Invalid refresh token')
            return jsonify({
                'error': 'invalid_grant',
                'error_description': 'Invalid or expired refresh token'
            }), 400
        
        token.is_revoked = True
        db.session.commit()
        
        new_token_data = create_token(client, token.user_id, token.scope, 'refresh_token')
        
        log_request(
            'token_success',
            client_id=client.client_id,
            user_id=token.user_id,
            grant_type=grant_type,
            scope=token.scope,
            success=True
        )
        
        return jsonify(new_token_data)
    
    else:
        log_request('token_error', client_id=client.client_id, grant_type=grant_type, success=False, error_message='Unsupported grant type')
        return jsonify({
            'error': 'unsupported_grant_type',
            'error_description': 'Unsupported grant type'
        }), 400

@oauth_bp.route('/introspect', methods=['POST'])
@require_basic_auth
def introspect():
    sim_error = check_simulated_error('invalid_token')
    if sim_error:
        log_request('introspect_error', client_id=request.client.client_id, success=False, error_message=sim_error[0]['error_description'])
        return jsonify({'active': False}), 200
    
    token_str = request.form.get('token')
    token_type_hint = request.form.get('token_type_hint', 'access_token')
    
    if not token_str:
        log_request('introspect_error', client_id=request.client.client_id, success=False, error_message='Missing token')
        return jsonify({'active': False}), 200
    
    token, error = validate_token(token_str)
    
    log_request(
        'introspect',
        client_id=request.client.client_id,
        user_id=token.user_id if token else None,
        success=token is not None,
        error_message=error
    )
    
    if not token:
        return jsonify({'active': False}), 200
    
    return jsonify(token.to_introspect()), 200

@oauth_bp.route('/revoke', methods=['POST'])
@require_basic_auth
def revoke():
    token_str = request.form.get('token')
    token_type_hint = request.form.get('token_type_hint', 'access_token')
    
    if not token_str:
        return '', 200
    
    token = Token.query.filter_by(
        client_id=request.client.client_id,
        is_revoked=False
    ).filter(
        (Token.access_token == token_str) | (Token.refresh_token == token_str)
    ).first()
    
    if token:
        token.is_revoked = True
        db.session.commit()
        
        log_request(
            'token_revoke',
            client_id=request.client.client_id,
            user_id=token.user_id,
            success=True
        )
    
    return '', 200

def redirect_with_error(redirect_uri, error, error_description, state=None):
    params = {
        'error': error,
        'error_description': error_description
    }
    if state:
        params['state'] = state
    
    parsed = urlparse(redirect_uri)
    existing_params = parse_qs(parsed.query)
    existing_params.update(params)
    
    new_query = urlencode({k: v[0] if isinstance(v, list) else v for k, v in existing_params.items()})
    new_url = urlunparse(parsed._replace(query=new_query))
    
    return redirect(new_url)
