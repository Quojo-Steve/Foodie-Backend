from flask import Flask, request, jsonify, session
from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt
from flask_mail import Mail, Message
from datetime import datetime, timedelta
import sqlite3
import secrets
import json
import os
from functools import wraps
from dotenv import load_dotenv
import requests
from groq import Groq

# Load environment variables
load_dotenv()

app = Flask(__name__)
YOUTUBE_API_KEY = "AIzaSyAy6x8utPLPPyt_4thV9JKdv3OUHQGLPNI"
PEXELS_API_KEY = "HkCVDhZhSeEIA3UCyGtVr4IPKtsamjfMYIZAivNiMVGv1o2iTqFCwSIt"
G_API_KEY="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"
# Initialize Groq client
client = Groq(api_key=G_API_KEY)

# Configuration from environment variables
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', '3f9b3cd3a4bc4f2181d62e9f4e6e1e96bff932a3ddce781c72c7be8d6e3bb654')
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URI', 'sqlite:///foodie.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Email configuration
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = os.getenv('EMAIL_USER', '0320080067@htu.edu.gh')
app.config['MAIL_PASSWORD'] = os.getenv('EMAIL_PASS', 'xbmhdwfpqodawdzh')
app.config['MAIL_DEFAULT_SENDER'] = os.getenv('EMAIL_USER', '0320080067@htu.edu.gh')

# Initialize extensions
db = SQLAlchemy(app)
bcrypt = Bcrypt(app)
mail = Mail(app)

# Database Models
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    phone_number = db.Column(db.String(20), nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    is_verified = db.Column(db.Boolean, default=False)
    otp_code = db.Column(db.String(6))
    otp_expiry = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    preferences = db.relationship('UserPreference', backref='user', uselist=False)
    saved_recipes = db.relationship('SavedRecipe', backref='user')

class UserPreference(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    diet_type = db.Column(db.String(50))
    allergies = db.Column(db.String(100))
    cuisine = db.Column(db.String(50))
    cooking_method = db.Column(db.String(50))
    exclusions = db.Column(db.String(100))
    updated_at = db.Column(db.DateTime, default=datetime.utcnow)

class Recipe(db.Model):
    id = db.Column(db.String(50), primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    ingredients = db.Column(db.Text, nullable=False)  # JSON string
    directions = db.Column(db.Text, nullable=False)   # JSON string
    rating = db.Column(db.Float, default=0.0)
    time = db.Column(db.String(20))
    category = db.Column(db.String(50))
    image_path = db.Column(db.String(200))
    video_url = db.Column(db.String(500))
    country = db.Column(db.String(50))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class SavedRecipe(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    recipe_id = db.Column(db.String(50), db.ForeignKey('recipe.id'), nullable=False)
    saved_at = db.Column(db.DateTime, default=datetime.utcnow)

# Utility Functions
def generate_otp():
    return str(secrets.randbelow(1000000)).zfill(6)

def send_otp_email(email, otp):
    try:
        msg = Message(
            'Email Verification - Recipe App',
            recipients=[email],
            html=f'''
            <h2>Welcome to Recipe App!</h2>
            <p>Your verification code is: <strong style="font-size: 24px; color: #007bff;">{otp}</strong></p>
            <p>This code will expire in 10 minutes.</p>
            <p>If you didn't create an account, please ignore this email.</p>
            '''
        )
        mail.send(msg)
        return True
    except Exception as e:
        print(f"Email sending failed: {e}")
        return False

def validate_password(password):
    return len(password) >= 6

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return jsonify({'error': 'Authentication required'}), 401
        return f(*args, **kwargs)
    return decorated_function

def fetch_pinterest_image(query):
    try:
        search_url = f"https://www.pinterest.com/search/pins/?q={query.replace(' ', '%20')}"
        res = requests.get(search_url, timeout=5)

        if res.status_code == 200:
            html = res.text
            # find first <img src="...">
            start = html.find('src="') + 5
            end = html.find('"', start)
            if start > 4 and end > start:
                return html[start:end]
    except Exception as e:
        print(f"Pinterest fetch error: {e}")
    return None

# Routes

@app.route('/api/signup', methods=['POST'])
def signup():
    try:
        data = request.get_json()
        email = data.get('email', '').lower().strip()
        phone_number = data.get('phone_number', '').strip()
        password = data.get('password', '')
        print(data)
        # Validation
        if not email or not phone_number or not password:
            return jsonify({'error': 'All fields are required'}), 400

        if not validate_password(password):
            return jsonify({'error': 'Password must be at least 6 characters'}), 400

        # Check if user already exists
        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            return jsonify({'error': 'Email already registered'}), 409

        # Generate OTP
        otp = generate_otp()
        otp_expiry = datetime.utcnow() + timedelta(minutes=10)

        # Hash password
        password_hash = bcrypt.generate_password_hash(password).decode('utf-8')

        # Create user
        user = User(
            email=email,
            phone_number=phone_number,
            password_hash=password_hash,
            otp_code=otp,
            otp_expiry=otp_expiry
        )

        db.session.add(user)
        db.session.commit()

        # Send OTP email
        if send_otp_email(email, otp):
            return jsonify({
                'message': 'Account created successfully. Please check your email for verification code.',
                'user_id': user.id
            }), 201
        else:
            return jsonify({'error': 'Account created but failed to send verification email'}), 500

    except Exception as e:
        db.session.rollback()
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/api/verify-otp', methods=['POST'])
def verify_otp():
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        otp = data.get('otp')
        print(data)
        if not user_id or not otp:
            return jsonify({'error': 'User ID and OTP are required'}), 400

        user = User.query.get(user_id)
        if not user:
            return jsonify({'error': 'User not found'}), 404

        if user.is_verified:
            return jsonify({'error': 'Account already verified'}), 400

        if datetime.utcnow() > user.otp_expiry:
            return jsonify({'error': 'OTP expired'}), 400

        if user.otp_code != otp:
            return jsonify({'error': 'Invalid OTP'}), 400

        # Verify user
        user.is_verified = True
        user.otp_code = None
        user.otp_expiry = None
        db.session.commit()

        return jsonify({'message': 'Email verified successfully'}), 200

    except Exception as e:
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/api/signin', methods=['POST'])
def signin():
    try:
        data = request.get_json()
        email = data.get('email', '').lower().strip()
        password = data.get('password', '')

        if not email or not password:
            return jsonify({'error': 'Email and password are required'}), 400

        user = User.query.filter_by(email=email).first()
        if not user:
            return jsonify({'error': 'Invalid email or password'}), 401

        if not user.is_verified:
            return jsonify({'error': 'Please verify your email before signing in'}), 401

        if not bcrypt.check_password_hash(user.password_hash, password):
            return jsonify({'error': 'Invalid email or password'}), 401

        # Create session
        session['user_id'] = user.id
        session['user_email'] = user.email

        return jsonify({
            'message': 'Signed in successfully',
            'user': {
                'id': user.id,
                'email': user.email,
                'phone_number': user.phone_number
            }
        }), 200

    except Exception as e:
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/api/signout', methods=['POST'])
@login_required
def signout():
    session.clear()
    return jsonify({'message': 'Signed out successfully'}), 200

@app.route('/api/preferences', methods=['POST', 'GET'])
def user_preferences():
    if request.method == 'POST':
        try:
            data = request.get_json()
            user_id = data.get('user_id')   # get directly from frontend

            if not user_id:
                return jsonify({'error': 'user_id is required'}), 400

            preferences = UserPreference.query.filter_by(user_id=user_id).first()

            if preferences:
                # Update existing preferences
                preferences.diet_type = data.get('diet_type')
                preferences.allergies = data.get('allergies')
                preferences.cuisine = data.get('cuisine')
                preferences.cooking_method = data.get('cooking_method')
                preferences.exclusions = data.get('exclusions')
                preferences.updated_at = datetime.utcnow()
            else:
                # Create new preferences
                preferences = UserPreference(
                    user_id=user_id,
                    diet_type=data.get('diet_type'),
                    allergies=data.get('allergies'),
                    cuisine=data.get('cuisine'),
                    cooking_method=data.get('cooking_method'),
                    exclusions=data.get('exclusions')
                )
                db.session.add(preferences)

            db.session.commit()
            return jsonify({'message': 'Preferences saved successfully'}), 200

        except Exception as e:
            db.session.rollback()
            return jsonify({'error': str(e)}), 500

    else:  # GET request
        user_id = request.args.get('user_id')   # read from query param
        if not user_id:
            return jsonify({'error': 'user_id is required'}), 400

        preferences = UserPreference.query.filter_by(user_id=user_id).first()
        if preferences:
            return jsonify({
                'diet_type': preferences.diet_type,
                'allergies': preferences.allergies,
                'cuisine': preferences.cuisine,
                'cooking_method': preferences.cooking_method,
                'exclusions': preferences.exclusions
            }), 200
        else:
            return jsonify({
                'diet_type': None,
                'allergies': None,
                'cuisine': None,
                'cooking_method': None,
                'exclusions': None
            }), 200

@app.route('/api/recipes', methods=['GET'])
def get_recipes():
    try:
        recipes = Recipe.query.all()
        recipe_list = []
        
        for recipe in recipes:
            recipe_data = {
                'id': recipe.id,
                'title': recipe.title,
                'ingredients': json.loads(recipe.ingredients),
                'directions': json.loads(recipe.directions),
                'rating': recipe.rating,
                'time': recipe.time,
                'category': recipe.category,
                'image': recipe.image_path,
                'videoUrl': recipe.video_url,
                'country': recipe.country
            }
            recipe_list.append(recipe_data)
        
        return jsonify({'recipes': recipe_list}), 200
        
    except Exception as e:
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/api/recipes/<recipe_id>', methods=['GET'])
def get_recipe(recipe_id):
    try:
        recipe = Recipe.query.get(recipe_id)
        if not recipe:
            return jsonify({'error': 'Recipe not found'}), 404
        
        recipe_data = {
            'id': recipe.id,
            'title': recipe.title,
            'ingredients': json.loads(recipe.ingredients),
            'directions': json.loads(recipe.directions),
            'rating': recipe.rating,
            'time': recipe.time,
            'category': recipe.category,
            'image': recipe.image_path,
            'videoUrl': recipe.video_url,
            'country': recipe.country
        }
        
        return jsonify(recipe_data), 200
        
    except Exception as e:
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/api/recipes', methods=['POST'])
def add_recipe():
    try:
        data = request.get_json()
        
        # Validation
        required_fields = ['id', 'title', 'ingredients', 'directions']
        for field in required_fields:
            if field not in data:
                return jsonify({'error': f'{field} is required'}), 400
        
        # Check if recipe ID already exists
        existing_recipe = Recipe.query.get(data['id'])
        if existing_recipe:
            return jsonify({'error': 'Recipe ID already exists'}), 409
        
        recipe = Recipe(
            id=data['id'],
            title=data['title'],
            ingredients=json.dumps(data['ingredients']),
            directions=json.dumps(data['directions']),
            rating=data.get('rating', 0.0),
            time=data.get('time'),
            category=data.get('category'),
            image_path=data.get('image'),
            video_url=data.get('videoUrl'),
            country=data.get('country')
        )
        
        db.session.add(recipe)
        db.session.commit()
        
        return jsonify({'message': 'Recipe added successfully'}), 201
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/api/save-recipe', methods=['POST'])
def save_recipe():
    try:
        data = request.get_json()
        recipe_id = data.get('recipe_id')
        user_id = data.get('user_id')
        
        if not recipe_id:
            return jsonify({'error': 'Recipe ID is required'}), 400
        
        # Check if recipe exists
        recipe = Recipe.query.get(recipe_id)
        if not recipe:
            return jsonify({'error': 'Recipe not found'}), 404
        
        # Check if already saved
        existing_save = SavedRecipe.query.filter_by(
            user_id=user_id, 
            recipe_id=recipe_id
        ).first()
        
        if existing_save:
            return jsonify({'error': 'Recipe already saved'}), 409
        
        saved_recipe = SavedRecipe(user_id=user_id, recipe_id=recipe_id)
        db.session.add(saved_recipe)
        db.session.commit()
        
        return jsonify({'message': 'Recipe saved successfully'}), 201
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/api/saved-recipes', methods=['GET'])
def get_saved_recipes():
    try:
        user_id = session['user_id']
        
        saved_recipes = db.session.query(Recipe).join(
            SavedRecipe, Recipe.id == SavedRecipe.recipe_id
        ).filter(SavedRecipe.user_id == user_id).all()
        
        recipe_list = []
        for recipe in saved_recipes:
            recipe_data = {
                'id': recipe.id,
                'title': recipe.title,
                'ingredients': json.loads(recipe.ingredients),
                'directions': json.loads(recipe.directions),
                'rating': recipe.rating,
                'time': recipe.time,
                'category': recipe.category,
                'image': recipe.image_path,
                'videoUrl': recipe.video_url,
                'country': recipe.country
            }
            recipe_list.append(recipe_data)
        
        return jsonify({'saved_recipes': recipe_list}), 200
        
    except Exception as e:
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/', methods=['GET'])
def health_check():
    return jsonify({"message": "working"})

@app.route('/api/remove-saved-recipe', methods=['DELETE'])
def remove_saved_recipe():
    try:
        data = request.get_json()
        recipe_id = data.get('recipe_id')
        user_id = data.get('user_id')
        
        if not recipe_id:
            return jsonify({'error': 'Recipe ID is required'}), 400
        
        saved_recipe = SavedRecipe.query.filter_by(
            user_id=user_id, 
            recipe_id=recipe_id
        ).first()
        
        if not saved_recipe:
            return jsonify({'error': 'Saved recipe not found'}), 404
        
        db.session.delete(saved_recipe)
        db.session.commit()
        
        return jsonify({'message': 'Recipe removed from saved list'}), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/api/generate-recipes', methods=['POST'])
def generate_recipes():
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        custom_text = data.get('custom_text', "")

        if not user_id:
            return jsonify({'error': 'user_id is required'}), 400

        user_pref = UserPreference.query.filter_by(user_id=user_id).first()

        preferences_text = ""
        if user_pref:
            preferences_text = f"""
            Diet type: {user_pref.diet_type or "None"}
            Allergies: {user_pref.allergies or "None"}
            Preferred cuisine: {user_pref.cuisine or "None"}
            Cooking method: {user_pref.cooking_method or "None"}
            Exclusions: {user_pref.exclusions or "None"}
            """

        prompt = f"""
            Generate exactly 5 structured recipes as a JSON array.
            Each recipe must have these exact fields:
            "id" (string), "title" (string), "ingredients" (array of strings), 
            "directions" (array of strings), "rating" (number between 1-5),
            "time" (string like "30 min"), "category" (string), "country" (string).

            User preferences:
            {preferences_text}

            User ingredients/requirements:
            {custom_text}

            Return ONLY the JSON array, no explanations or extra text.
            Example format: [{{"id": "1", "title": "Recipe Name", "ingredients": ["item1", "item2"], "directions": ["step1", "step2"], "rating": 4.5, "time": "30 min", "category": "Main", "country": "Ghana"}}]
            """

        # Use Groq AI
        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",  # Current available models
            # Alternative models: "llama-3.2-90b-text-preview", "mixtral-8x7b-32768", "gemma2-9b-it"
            messages=[
                {"role": "system", "content": "You are a professional chef. Always respond with valid JSON only."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=2000,
            temperature=0.7
        )


        recipes_json = response.choices[0].message.content
        #print(f"Groq Response: {recipes_json}")  # Debug log

        # Clean the response (remove any markdown or extra text)
        recipes_json = recipes_json.strip()
        if recipes_json.startswith('```json'):
            recipes_json = recipes_json[7:]
        if recipes_json.endswith('```'):
            recipes_json = recipes_json[:-3]
        recipes_json = recipes_json.strip()

        recipes_data = json.loads(recipes_json)

        enriched_recipes = []

        for i, r in enumerate(recipes_data):
            try:
                # Ensure required fields exist
                recipe_id = r.get('id', f"groq_{i+1}")
                title = r.get('title', f'Generated Recipe {i+1}')
                
                # 🔹 Fetch a YouTube tutorial
                video_url = None
                if YOUTUBE_API_KEY:
                    try:
                        yt_url = f"https://www.googleapis.com/youtube/v3/search?part=snippet&q=how+to+make+{title}&key={YOUTUBE_API_KEY}"
                        yt_res = requests.get(yt_url, timeout=5).json()
                        if "items" in yt_res and yt_res["items"]:
                            video_url = f"https://www.youtube.com/watch?v={yt_res['items'][0]['id']['videoId']}"
                    except Exception as e:
                        print(f"YouTube API error: {e}")

                # 🔹 Fetch an image (Pexels or Unsplash)
                image_url = None
                if PEXELS_API_KEY:
                    try:
                        img_url = f"https://api.pexels.com/v1/search?query={title}&per_page=1"
                        img_res = requests.get(img_url, headers={"Authorization": PEXELS_API_KEY}, timeout=5).json()
                        if img_res.get('photos'):
                            image_url = img_res['photos'][0]['src']['medium']
                    except Exception as e:
                        print(f"Pexels API error: {e}")
                
                # Fallback image
                if not image_url:
                    image_url = f"https://source.unsplash.com/800x600/?food,{title.replace(' ', '+')}"               
                
                # Add image_url to response
                r['image'] = image_url
                r['videoUrl'] = video_url
                enriched_recipes.append(r)
                
            except Exception as recipe_error:
                print(f"Error processing recipe {i}: {recipe_error}")
                continue
            
        db.session.commit()

        return jsonify({'recipes': enriched_recipes}), 200

    except json.JSONDecodeError as e:
        print(f"JSON parsing error: {e}")
        return jsonify({'error': f'Invalid JSON response from AI: {str(e)}'}), 500
    except Exception as e:
        print(f"Error: {e}")
        return jsonify({'error': str(e)}), 500
    
# Initialize database
def init_db():
    with app.app_context():
        db.create_all()
        
        # Add sample recipes if none exist
        if Recipe.query.count() == 0:
            sample_recipes = [
                {
                    'id': '1',
                    'title': 'Crispy Fried Chicken',
                    'ingredients': [
                        'Chicken drumsticks', 'Buttermilk', 'All-purpose flour', 
                        'Paprika', 'Garlic powder', 'Salt', 'Black pepper', 'Vegetable oil'
                    ],
                    'directions': [
                        'Marinate chicken in buttermilk for 4 hours.',
                        'Mix flour and spices in a bowl.',
                        'Coat chicken in flour mixture.',
                        'Fry in hot oil until golden and cooked through.'
                    ],
                    'rating': 4.7,
                    'time': '30 min',
                    'category': 'Dinner',
                    'image': 'https://thissillygirlskitchen.com/wp-content/uploads/2012/09/Grandmas-Fried-Chicken-21.jpg',
                    'videoUrl': 'https://www.youtube.com/watch?v=6tw9jOBEXzI',
                    'country': 'Ghana'
                },
                {
                    'id': '2',
                    'title': 'Jollof Rice',
                    'ingredients': [
                        'Rice', 'Tomatoes', 'Onions', 'Pepper', 'Chicken stock', 
                        'Thyme', 'Bay leaves', 'Curry powder', 'Salt'
                    ],
                    'directions': [
                        'Blend tomatoes, onions and peppers.',
                        'Fry the blend until reduced.',
                        'Add rice and stock.',
                        'Cook until rice is tender.'
                    ],
                    'rating': 4.9,
                    'time': '45 min',
                    'category': 'Lunch',
                    'image': 'https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcR_IAuXn-90FRCnOoccQWxuvzV7Ge16qv-0PA&s',
                    'videoUrl': 'https://www.youtube.com/watch?v=example',
                    'country': 'Ghana'
                }
            ]
            
            for recipe_data in sample_recipes:
                recipe = Recipe(
                    id=recipe_data['id'],
                    title=recipe_data['title'],
                    ingredients=json.dumps(recipe_data['ingredients']),
                    directions=json.dumps(recipe_data['directions']),
                    rating=recipe_data['rating'],
                    time=recipe_data['time'],
                    category=recipe_data['category'],
                    image_path=recipe_data['image'],
                    video_url=recipe_data['videoUrl'],
                    country=recipe_data['country']
                )
                db.session.add(recipe)
            
            db.session.commit()

if __name__ == '__main__':
    init_db()
    app.run(debug=True, host='0.0.0.0', port=5000)