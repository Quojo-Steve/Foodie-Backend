from flask import Blueprint, request, jsonify
from app.extensions import db
from app.models import User
from app.utils.email import send_otp_email, generate_otp
from werkzeug.security import generate_password_hash
from datetime import datetime, timedelta

auth = Blueprint('auth', __name__)

@auth.route('/signup', methods=['POST'])
def signup():
    data = request.get_json()
    email = data['email']
    password = generate_password_hash(data['password'])
    
    if User.query.filter_by(email=email).first():
        return jsonify({'error': 'Email already exists'}), 400

    otp = generate_otp()
    otp_expiry = datetime.utcnow() + timedelta(minutes=10)

    user = User(email=email, password=password, otp_code=otp, otp_expiry=otp_expiry)
    db.session.add(user)
    db.session.commit()

    send_otp_email(email, otp)

    return jsonify({'message': 'Signup successful, OTP sent to email'}), 201

@auth.route('/verify-otp', methods=['POST'])
def verify_otp():
    data = request.get_json()
    email = data['email']
    otp = data['otp']

    user = User.query.filter_by(email=email).first()

    if not user or user.otp_code != otp or user.otp_expiry < datetime.utcnow():
        return jsonify({'error': 'Invalid or expired OTP'}), 400

    user.is_verified = True
    user.otp_code = None
    user.otp_expiry = None
    db.session.commit()

    return jsonify({'message': 'Email verified successfully'}), 200
