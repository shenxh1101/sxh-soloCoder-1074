import secrets
from flask import Blueprint, request, render_template, redirect, url_for, session, make_response
from app.utils import log_request

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    next_url = request.args.get('next', '/')
    
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        
        if not username:
            return render_template('login.html',
                next=next_url,
                error='Please enter a username'
            )
        
        session_id = secrets.token_hex(16)
        session[f'user_{session_id}'] = username
        session.permanent = True
        
        log_request(
            'login',
            user_id=username,
            success=True
        )
        
        resp = make_response(redirect(next_url))
        resp.set_cookie('oauth_session', session_id, max_age=86400)
        return resp
    
    return render_template('login.html', next=next_url)

@auth_bp.route('/logout')
def logout():
    session_id = request.cookies.get('oauth_session')
    if session_id and f'user_{session_id}' in session:
        user_id = session.pop(f'user_{session_id}')
        log_request('logout', user_id=user_id, success=True)
    
    resp = make_response(redirect(url_for('main.index')))
    resp.delete_cookie('oauth_session')
    return resp
