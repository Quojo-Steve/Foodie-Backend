from app.extensions import mail
import random
from flask_mail import Message

def generate_otp():
    return str(random.randint(100000, 999999))

def send_otp_email(email, otp):
    msg = Message("Your OTP Code", recipients=[email])
    msg.body = f"Your OTP is: {otp}. It will expire in 10 minutes."
    mail.send(msg)
