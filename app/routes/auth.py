from flask import Blueprint, request, jsonify
from app.extensions import db
from app.models import User
from app.utils.email import send_otp_email, generate_otp
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta

auth = Blueprint('auth', __name__)

@auth.route('/signup', methods=['POST'])
def signup():
    data = request.get_json()
    email = data['email']
    password = generate_password_hash(data['password'])
    phone_number = data['phone']
    
    if User.query.filter_by(email=email).first():
        return jsonify({'error': 'Email already exists'}), 400

    otp = generate_otp()
    otp_expiry = datetime.utcnow() + timedelta(minutes=10)

    user = User(email=email, password=password, otp_code=otp, otp_expiry=otp_expiry, phone_number=phone_number)
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

@auth.route('/signin', methods=['POST'])
def signin():
    data = request.get_json()
    email = data.get('email')
    password = data.get('password')

    if not email or not password:
        return jsonify({'error': 'Email and password are required'}), 400

    user = User.query.filter_by(email=email).first()

    if not user:
        return jsonify({'error': 'Invalid email or password'}), 401

    if not check_password_hash(user.password, password):
        return jsonify({'error': 'Invalid email or password'}), 401

    if not user.is_verified:
        return jsonify({'error': 'Email not verified. Please check your inbox.'}), 403

    # You could generate a token here (e.g., JWT) for session-based login
    return jsonify({
        'message': 'Login successful',
        'user': {
            'id': user.id,
            'email': user.email
        }
    }), 200

def resend_otp():
    data = request.get_json()
    email = data.get('email')

    if not email:
        return jsonify({'error': 'Email is required'}), 400

    user = User.query.filter_by(email=email).first()

    if not user:
        return jsonify({'error': 'User not found'}), 404

    if user.is_verified:
        return jsonify({'error': 'User already verified'}), 400

    try:
        otp = generate_otp()
        user.otp = otp
        user.otp_expiry = datetime.utcnow() + timedelta(minutes=10)
        db.session.commit()

        send_otp_email(user.email, otp)

        return jsonify({'message': 'A new OTP has been sent to your email'}), 200

    except Exception as e:
        print("Error during resend OTP:", e)
        return jsonify({'error': 'Failed to resend OTP'}), 500