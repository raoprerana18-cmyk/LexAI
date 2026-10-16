from flask import Flask, render_template, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_bcrypt import Bcrypt
import os
from config import Config

from extensions import db, bcrypt, login_manager

@login_manager.user_loader
def load_user(user_id):
    from models.database_models import User
    return db.session.get(User, int(user_id))


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    # Initialize extensions with app
    db.init_app(app)
    bcrypt.init_app(app)
    login_manager.init_app(app)

    # Register blueprints
    from routes.auth_routes import auth_bp
    from routes.document_routes import document_bp
    from routes.chat_routes import chat_bp
    from routes.admin_routes import admin_bp
    from routes.main_routes import main_bp
    
    app.register_blueprint(auth_bp)
    app.register_blueprint(document_bp)
    app.register_blueprint(chat_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(main_bp)

    # Custom error handlers
    from flask import request
    
    @app.errorhandler(403)
    def forbidden(e):
        if request.path.startswith('/api/'):
            return jsonify({"error": "Forbidden"}), 403
        return render_template('403.html'), 403

    @app.errorhandler(404)
    def page_not_found(e):
        if request.path.startswith('/api/'):
            return jsonify({"error": "Not Found"}), 404
        return render_template('404.html'), 404

    @app.errorhandler(500)
    def internal_server_error(e):
        if request.path.startswith('/api/'):
            return jsonify({"error": "Internal Server Error"}), 500
        return render_template('500.html'), 500

    return app

if __name__ == '__main__':
    app = create_app()
    debug_mode = os.getenv('FLASK_DEBUG', 'False').lower() in ('1', 'true', 'yes')
    app.run(host='0.0.0.0', debug=debug_mode, port=5000)
