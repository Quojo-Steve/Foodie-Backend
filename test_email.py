from flask import Flask
from flask_mail import Mail, Message
from dotenv import load_dotenv
import os

# Load .env values
load_dotenv()

app = Flask(__name__)

# Configure Flask-Mail
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = os.getenv("EMAIL_USER")
app.config['MAIL_PASSWORD'] = os.getenv("EMAIL_PASS")
app.config['MAIL_DEFAULT_SENDER'] = os.getenv("EMAIL_USER")

mail = Mail(app)

with app.app_context():
    try:
        msg = Message("🚀 Test Email from Flask",
                      recipients=["ahmedashafa12@gmail.com"])
        msg.body = "This is a test message to confirm your Flask email config works!"
        mail.send(msg)
        print("✅ Email sent successfully!")
    except Exception as e:
        print("❌ Failed to send email.")
        print(e)
