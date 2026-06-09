from flask import Blueprint, render_template, request, redirect, url_for, jsonify, session
from app import db
from app.models import Token, Client, SimulatedError, Scope, Log
from app.utils import log_request

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
    tokens = Token.query.order_by(Token.created_at.desc()).limit(200).all()
    clients = Client.query.all()
    client_map = {c.client_id: c.name for c in clients}
    
    filter_client = request.args.get('client_id', '')
    filter_status = request.args.get('status', 'all')
    
    if filter_client:
        tokens = [t for t in tokens if t.client_id == filter_client]
    
    if filter_status == 'active':
        tokens = [t for t in tokens if t.is_active()]
    elif filter_status == 'revoked':
        tokens = [t for t in tokens if t.is_revoked]
    elif filter_status == 'expired':
        tokens = [t for t in tokens if t.is_expired() and not t.is_revoked]
    
    return render_template('admin_tokens.html',
        tokens=tokens,
        clients=clients,
        client_map=client_map,
        filter_client=filter_client,
        filter_status=filter_status
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
        error = SimulatedError(
            name=request.form['name'],
            description=request.form.get('description', ''),
            error_type=request.form['error_type'],
            status_code=int(request.form.get('status_code', 400)),
            error_message=request.form.get('error_message', ''),
            enabled=False
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
    return render_template('simulated_error_form.html', error=None, error_types=error_types)

@admin_bp.route('/simulated-errors/<int:error_id>/edit', methods=['GET', 'POST'])
def edit_simulated_error(error_id):
    error = SimulatedError.query.get_or_404(error_id)
    
    if request.method == 'POST':
        error.name = request.form['name']
        error.description = request.form.get('description', '')
        error.error_type = request.form['error_type']
        error.status_code = int(request.form.get('status_code', 400))
        error.error_message = request.form.get('error_message', '')
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
    return render_template('simulated_error_form.html', error=error, error_types=error_types)

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
