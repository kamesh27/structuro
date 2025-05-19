from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from . import db
from datetime import datetime

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256)) # Increased length for potentially longer hashes

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    calculations = db.relationship('CalculationHistory', backref='user', lazy=True)

    def __repr__(self):
        return f'<User {self.username}>'

class CalculationHistory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    timestamp = db.Column(db.DateTime, index=True, default=datetime.utcnow)
    input_parameters = db.Column(db.Text, nullable=False) # Storing as JSON string
    results = db.Column(db.Text, nullable=False) # Storing as JSON string

    def __repr__(self):
        return f'<CalculationHistory {self.id} by User {self.user_id} at {self.timestamp}>'
