import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from dotenv import load_dotenv

load_dotenv()

db = SQLAlchemy()

def create_app():
    app = Flask(__name__, template_folder='templates', static_folder='static')
    
    app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')
    app.config['JWT_SECRET_KEY'] = os.getenv('JWT_SECRET_KEY', 'jwt-secret-key-change-in-production')
    app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'sqlite:///oauth_server.db')
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['TOKEN_EXPIRE_SECONDS'] = int(os.getenv('TOKEN_EXPIRE_SECONDS', 3600))
    app.config['AUTH_CODE_EXPIRE_SECONDS'] = int(os.getenv('AUTH_CODE_EXPIRE_SECONDS', 600))
    
    db.init_app(app)
    
    from app.routes.main import main_bp
    from app.routes.oauth import oauth_bp
    from app.routes.admin import admin_bp
    from app.routes.api import api_bp
    from app.routes.auth import auth_bp
    
    app.register_blueprint(main_bp)
    app.register_blueprint(oauth_bp, url_prefix='/oauth')
    app.register_blueprint(admin_bp, url_prefix='/admin')
    app.register_blueprint(api_bp, url_prefix='/api')
    app.register_blueprint(auth_bp)
    
    with app.app_context():
        db.create_all()
        from app.models import Scope
        if not Scope.query.first():
            default_scopes = ['read:user', 'write:data', 'read:data', 'admin', 'profile', 'email']
            for scope_name in default_scopes:
                scope = Scope(name=scope_name, description=f'{scope_name} scope')
                db.session.add(scope)
            db.session.commit()
    
    return app
