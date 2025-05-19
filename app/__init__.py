import os
import json # Import json
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager

db = SQLAlchemy()
login_manager = LoginManager()

# Custom Jinja filter
def from_json_filter(value):
    try:
        return json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return {} # Return empty dict or handle error as appropriate

def create_app(test_config=None):
    """Create and configure an instance of the Flask application."""
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_mapping(
        SECRET_KEY=os.environ.get('SECRET_KEY', 'dev_secret_key'), # Use environment variable in production
        SQLALCHEMY_DATABASE_URI=f"sqlite:///{os.path.join(app.instance_path, 'app.db')}",
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
    )

    if test_config is None:
        # load the instance config, if it exists, when not testing
        app.config.from_pyfile('config.py', silent=True)
    else:
        # load the test config if passed in
        app.config.update(test_config)

    # ensure the instance folder exists
    try:
        os.makedirs(app.instance_path)
    except OSError:
        pass

    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login' # The route for login

    # Import and register blueprints here
    from . import auth
    app.register_blueprint(auth.bp)

    from . import main_routes # Import the new main routes
    app.register_blueprint(main_routes.main_bp) # Register the main blueprint

    # Import models here to ensure they are registered with SQLAlchemy
    from . import models

    with app.app_context():
        db.create_all() # Create database tables for our models

    # Register custom Jinja filter
    app.jinja_env.filters['fromjson'] = from_json_filter

    return app
