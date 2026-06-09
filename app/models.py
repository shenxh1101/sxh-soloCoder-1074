import secrets
import string
from datetime import datetime, timedelta, timezone
from app import db

def utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)

def generate_client_id():
    return ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(32))

def generate_client_secret():
    return ''.join(secrets.choice(string.ascii_letters + string.digits + '-_') for _ in range(64))

def generate_auth_code():
    return ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(40))

def generate_token_string():
    return ''.join(secrets.choice(string.ascii_letters + string.digits + '-._~+/') for _ in range(64))

class Client(db.Model):
    __tablename__ = 'clients'
    
    id = db.Column(db.Integer, primary_key=True)
    client_id = db.Column(db.String(64), unique=True, nullable=False, default=generate_client_id)
    client_secret = db.Column(db.String(128), nullable=False, default=generate_client_secret)
    name = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text)
    redirect_uris = db.Column(db.Text, nullable=False)
    grant_types = db.Column(db.String(255), default='authorization_code,client_credentials')
    token_format = db.Column(db.String(20), default='jwt')
    token_expire_seconds = db.Column(db.Integer, default=3600)
    require_consent = db.Column(db.Boolean, default=True)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=utcnow)
    
    def get_redirect_uris(self):
        return [uri.strip() for uri in self.redirect_uris.split(',') if uri.strip()]
    
    def get_grant_types(self):
        return [gt.strip() for gt in self.grant_types.split(',') if gt.strip()]
    
    def to_dict(self, include_secret=False):
        data = {
            'id': self.id,
            'client_id': self.client_id,
            'name': self.name,
            'description': self.description,
            'redirect_uris': self.get_redirect_uris(),
            'grant_types': self.get_grant_types(),
            'token_format': self.token_format,
            'token_expire_seconds': self.token_expire_seconds,
            'require_consent': self.require_consent,
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat()
        }
        if include_secret:
            data['client_secret'] = self.client_secret
        return data

class AuthorizationCode(db.Model):
    __tablename__ = 'authorization_codes'
    
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(80), unique=True, nullable=False, default=generate_auth_code)
    client_id = db.Column(db.String(64), db.ForeignKey('clients.client_id'), nullable=False)
    user_id = db.Column(db.String(255), nullable=False)
    redirect_uri = db.Column(db.String(500), nullable=False)
    scope = db.Column(db.String(500))
    expires_at = db.Column(db.DateTime, nullable=False)
    is_used = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    client = db.relationship('Client', backref=db.backref('authorization_codes', lazy=True))
    
    def is_expired(self):
        return utcnow() > self.expires_at
    
    def get_scope_list(self):
        return [s.strip() for s in (self.scope or '').split() if s.strip()]
    
    def to_dict(self):
        return {
            'code': self.code,
            'client_id': self.client_id,
            'user_id': self.user_id,
            'redirect_uri': self.redirect_uri,
            'scope': self.get_scope_list(),
            'expires_at': self.expires_at.isoformat(),
            'is_used': self.is_used,
            'created_at': self.created_at.isoformat()
        }

class Token(db.Model):
    __tablename__ = 'tokens'
    
    id = db.Column(db.Integer, primary_key=True)
    access_token = db.Column(db.String(500), unique=True, nullable=False)
    refresh_token = db.Column(db.String(500), unique=True)
    client_id = db.Column(db.String(64), db.ForeignKey('clients.client_id'), nullable=False)
    user_id = db.Column(db.String(255))
    token_type = db.Column(db.String(20), default='Bearer')
    scope = db.Column(db.String(500))
    expires_at = db.Column(db.DateTime, nullable=False)
    is_revoked = db.Column(db.Boolean, default=False)
    grant_type = db.Column(db.String(50))
    token_format = db.Column(db.String(20), default='jwt')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    client = db.relationship('Client', backref=db.backref('tokens', lazy=True))
    
    def is_expired(self):
        return utcnow() > self.expires_at
    
    def is_active(self):
        return not self.is_revoked and not self.is_expired()
    
    def get_scope_list(self):
        return [s.strip() for s in (self.scope or '').split() if s.strip()]
    
    def to_dict(self, include_token=True):
        data = {
            'id': self.id,
            'client_id': self.client_id,
            'user_id': self.user_id,
            'token_type': self.token_type,
            'scope': self.get_scope_list(),
            'expires_at': self.expires_at.isoformat(),
            'is_revoked': self.is_revoked,
            'grant_type': self.grant_type,
            'token_format': self.token_format,
            'created_at': self.created_at.isoformat(),
            'is_active': self.is_active()
        }
        if include_token:
            data['access_token'] = self.access_token
            data['refresh_token'] = self.refresh_token
        return data
    
    def to_introspect(self):
        return {
            'active': self.is_active(),
            'scope': self.scope,
            'client_id': self.client_id,
            'username': self.user_id,
            'token_type': self.token_type,
            'exp': int(self.expires_at.timestamp()),
            'iat': int(self.created_at.timestamp()),
            'token_format': self.token_format
        }

class Scope(db.Model):
    __tablename__ = 'scopes'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    description = db.Column(db.Text)
    is_enabled = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'is_enabled': self.is_enabled,
            'created_at': self.created_at.isoformat()
        }

class Log(db.Model):
    __tablename__ = 'logs'
    
    id = db.Column(db.Integer, primary_key=True)
    type = db.Column(db.String(50), nullable=False)
    endpoint = db.Column(db.String(200))
    method = db.Column(db.String(10))
    client_id = db.Column(db.String(64))
    user_id = db.Column(db.String(255))
    grant_type = db.Column(db.String(50))
    scope = db.Column(db.String(500))
    success = db.Column(db.Boolean, default=True)
    error_message = db.Column(db.Text)
    ip_address = db.Column(db.String(45))
    user_agent = db.Column(db.Text)
    request_data = db.Column(db.Text)
    response_data = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'type': self.type,
            'endpoint': self.endpoint,
            'method': self.method,
            'client_id': self.client_id,
            'user_id': self.user_id,
            'grant_type': self.grant_type,
            'scope': self.scope,
            'success': self.success,
            'error_message': self.error_message,
            'ip_address': self.ip_address,
            'created_at': self.created_at.isoformat()
        }

class SimulatedError(db.Model):
    __tablename__ = 'simulated_errors'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    description = db.Column(db.Text)
    enabled = db.Column(db.Boolean, default=False)
    error_type = db.Column(db.String(50), nullable=False)
    status_code = db.Column(db.Integer, default=401)
    error_message = db.Column(db.String(500))
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'enabled': self.enabled,
            'error_type': self.error_type,
            'status_code': self.status_code,
            'error_message': self.error_message
        }
