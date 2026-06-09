import json
import jwt
import secrets
from datetime import datetime, timedelta, timezone
from functools import wraps
from flask import request, jsonify, current_app
from app.models import Token, Log, SimulatedError, ErrorHit
from app import db

def generate_jwt_token(client_id, user_id, scope, expires_in):
    now = datetime.now(timezone.utc)
    payload = {
        'iss': 'oauth-server-simulator',
        'sub': user_id or client_id,
        'aud': client_id,
        'iat': int(now.timestamp()),
        'exp': int((now + timedelta(seconds=expires_in)).timestamp()),
        'client_id': client_id,
        'scope': scope,
        'jti': secrets.token_hex(16)
    }
    if user_id:
        payload['user_id'] = user_id
    return jwt.encode(payload, current_app.config['JWT_SECRET_KEY'], algorithm='HS256')

def generate_refresh_token():
    return secrets.token_urlsafe(64)

def create_token(client, user_id, scope, grant_type):
    token_format = client.token_format
    expires_in = client.token_expire_seconds
    
    if token_format == 'jwt':
        access_token = generate_jwt_token(client.client_id, user_id, scope, expires_in)
    else:
        from app.models import generate_token_string
        access_token = generate_token_string()
    
    refresh_token = generate_refresh_token()
    expires_at = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(seconds=expires_in)
    
    token = Token(
        access_token=access_token,
        refresh_token=refresh_token,
        client_id=client.client_id,
        user_id=user_id,
        scope=scope,
        expires_at=expires_at,
        grant_type=grant_type,
        token_format=token_format
    )
    db.session.add(token)
    db.session.commit()
    
    return {
        'access_token': access_token,
        'token_type': 'Bearer',
        'expires_in': expires_in,
        'refresh_token': refresh_token,
        'scope': scope
    }

def log_request(log_type, **kwargs):
    try:
        log = Log(
            type=log_type,
            endpoint=request.path,
            method=request.method,
            ip_address=request.remote_addr,
            user_agent=request.user_agent.string,
            request_data=json.dumps(request.args.to_dict() or request.form.to_dict() or {})[:1000],
            **kwargs
        )
        db.session.add(log)
        db.session.commit()
    except Exception as e:
        current_app.logger.error(f'Failed to log request: {e}')

def check_simulated_error(error_type, endpoint=None):
    query = SimulatedError.query.filter_by(error_type=error_type, enabled=True)
    errors = query.all()
    
    for error in errors:
        if endpoint is None or error.affects_endpoint(endpoint):
            try:
                client_id = None
                if hasattr(request, 'client') and request.client:
                    client_id = request.client.client_id
                else:
                    client_id = request.form.get('client_id') or request.args.get('client_id')
                    if not client_id and request.authorization:
                        client_id = request.authorization.username
                
                response_body = {
                    'error': error.error_type,
                    'error_description': error.error_message or f'Simulated {error.error_type} error'
                }
                
                error_hit = ErrorHit(
                    simulated_error_id=error.id,
                    endpoint=endpoint or 'unknown',
                    client_id=client_id,
                    error_type=error.error_type,
                    status_code=error.status_code,
                    error_message=error.error_message,
                    response_body=json.dumps(response_body),
                    request_path=request.path,
                    ip_address=request.remote_addr,
                    user_agent=request.user_agent.string[:500] if request.user_agent and request.user_agent.string else None
                )
                db.session.add(error_hit)
                db.session.commit()
            except Exception as e:
                current_app.logger.error(f'Failed to record error hit: {e}')
                db.session.rollback()
            
            return {
                'error': error.error_type,
                'error_description': error.error_message or f'Simulated {error.error_type} error'
            }, error.status_code
    return None

def require_basic_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth = request.authorization
        if not auth or not auth.username or not auth.password:
            log_request(
                'token_error',
                client_id=auth.username if auth else None,
                success=False,
                error_message='Missing client credentials'
            )
            return jsonify({
                'error': 'invalid_client',
                'error_description': 'Client authentication is required'
            }), 401
        
        from app.models import Client
        client = Client.query.filter_by(
            client_id=auth.username,
            client_secret=auth.password,
            is_active=True
        ).first()
        
        if not client:
            log_request(
                'token_error',
                client_id=auth.username,
                success=False,
                error_message='Invalid client credentials'
            )
            return jsonify({
                'error': 'invalid_client',
                'error_description': 'Invalid client credentials'
            }), 401
        
        request.client = client
        return f(*args, **kwargs)
    return decorated

def validate_token(token_str):
    token = Token.query.filter_by(access_token=token_str, is_revoked=False).first()
    if not token:
        return None, 'Invalid token'
    
    if token.is_expired():
        return None, 'Token expired'
    
    if token.token_format == 'jwt':
        try:
            jwt.decode(
                token_str, 
                current_app.config['JWT_SECRET_KEY'], 
                algorithms=['HS256'],
                audience=token.client_id,
                leeway=10
            )
        except jwt.ExpiredSignatureError:
            return None, 'Token expired'
        except jwt.InvalidTokenError as e:
            return None, f'Invalid token: {str(e)}'
    
    return token, None
