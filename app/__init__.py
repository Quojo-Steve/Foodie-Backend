from flask import Flask
from flask_cors import CORS
from .extensions import db, mail
from .routes.auth import auth
import os
from flask_mail import Mail

def create_app():
    app = Flask(__name__)
    app.config.from_object('config.Config')

    db.init_app(app)
    mail.init_app(app)
    CORS(app)

    app.register_blueprint(auth, url_prefix='/auth')

    with app.app_context():
        db.create_all()

    return app
