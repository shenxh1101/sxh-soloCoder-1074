from flask import Blueprint, render_template, redirect, url_for
from app.models import Client, Token, Log, Scope

main_bp = Blueprint('main', __name__)

@main_bp.route('/')
def index():
    clients = Client.query.order_by(Client.created_at.desc()).all()
    active_tokens = Token.query.filter_by(is_revoked=False).count()
    total_clients = Client.query.count()
    total_logs = Log.query.count()
    
    return render_template('index.html',
        clients=clients,
        active_tokens=active_tokens,
        total_clients=total_clients,
        total_logs=total_logs
    )

@main_bp.route('/clients')
def clients():
    clients = Client.query.order_by(Client.created_at.desc()).all()
    return render_template('clients.html', clients=clients)

@main_bp.route('/clients/<int:client_id>')
def client_detail(client_id):
    client = Client.query.get_or_404(client_id)
    tokens = Token.query.filter_by(client_id=client.client_id).order_by(Token.created_at.desc()).limit(20).all()
    return render_template('client_detail.html', client=client, tokens=tokens)

@main_bp.route('/clients/new')
def new_client():
    scopes = Scope.query.filter_by(is_enabled=True).all()
    return render_template('client_form.html', client=None, scopes=scopes)

@main_bp.route('/clients/<int:client_id>/edit')
def edit_client(client_id):
    client = Client.query.get_or_404(client_id)
    scopes = Scope.query.filter_by(is_enabled=True).all()
    return render_template('client_form.html', client=client, scopes=scopes)

@main_bp.route('/scopes')
def scopes():
    scopes = Scope.query.order_by(Scope.created_at.desc()).all()
    return render_template('scopes.html', scopes=scopes)

@main_bp.route('/logs')
def logs():
    logs = Log.query.order_by(Log.created_at.desc()).limit(100).all()
    return render_template('logs.html', logs=logs)

@main_bp.route('/docs')
def docs():
    return render_template('docs.html')
