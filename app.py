from flask import Flask, request, render_template, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
import logging
import secrets
import uuid
import random
from textblob import TextBlob

app = Flask(__name__)

# Generate and set the secret key
app.secret_key = secrets.token_hex(16)

# Configure the SQLite database
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///mood_tracker.db'
db = SQLAlchemy(app)

# Set up logging
logging.basicConfig(level=logging.DEBUG)

# Spotify API credentials
SPOTIPY_CLIENT_ID = 'f5d053f6cb124139a3d1e505d26635fc'
SPOTIPY_CLIENT_SECRET = '735bba397f424b49b387b56d264e7ed9'

# Configure Spotipy
sp = spotipy.Spotify(auth_manager=SpotifyClientCredentials(
    client_id=SPOTIPY_CLIENT_ID,
    client_secret=SPOTIPY_CLIENT_SECRET
))

# Define MoodEntry model with user_id
class MoodEntry(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String, nullable=False)
    date = db.Column(db.Date, nullable=False)
    emotion = db.Column(db.String, nullable=False)
    journal_entry = db.Column(db.String, nullable=False)

# Create tables
with app.app_context():
    db.create_all()

# --- Emotion detection (hybrid) ---
def get_emotion_from_text(text):
    text_lower = text.lower()
    joy_words = ["happy", "joy", "excited", "love", "glad", "amazing", "great", "wonderful", "fantastic", "fun"]
    sad_words = ["sad", "down", "unhappy", "depressed", "lonely", "miserable", "heartbroken", "upset"]
    anger_words = ["angry", "mad", "annoyed", "frustrated", "furious", "irritated", "rage", "hate"]
    fear_words = ["fear", "scared", "nervous", "anxious", "worried", "afraid", "terrified", "insecure"]
    calm_words = ["calm", "relaxed", "peaceful", "chill", "serene", "content"]
    tired_words = ["tired", "sleepy", "exhausted", "fatigued", "drowsy"]
    bored_words = ["bored", "boring", "dull", "uninterested", "apathetic"]

    def count_matches(words):
        return sum(word in text_lower for word in words)

    scores = {
        "Joy": count_matches(joy_words),
        "Sadness": count_matches(sad_words),
        "Anger": count_matches(anger_words),
        "Fear": count_matches(fear_words),
        "Calmness": count_matches(calm_words),
        "Tiredness": count_matches(tired_words),
        "Boredom": count_matches(bored_words),
    }

    if all(v == 0 for v in scores.values()):
        analysis = TextBlob(text)
        polarity = analysis.sentiment.polarity
        if polarity > 0.3:
            return "Joy"
        elif polarity < -0.3:
            return "Sadness"
        else:
            return "Neutral"

    emotion = max(scores, key=scores.get)
    return emotion if scores[emotion] > 0 else "Neutral"

# --- Spotify recommendations ---
def get_spotify_recommendations(emotion):
    emotion_genres = {
        'Joy': ["pop", "dance", "party"],
        'Sadness': ["blues", "acoustic", "piano"],
        'Anger': ["metal", "rock", "rap"],
        'Fear': ["ambient", "lofi", "soundtrack"],
        'Calmness': ["acoustic", "jazz", "chill"],
        'Tiredness': ["sleep", "chill", "ambient"],
        'Boredom': ["indie", "alt-rock", "electronic"],
        'Neutral': ["pop", "indie", "chill"]
    }
    genres = emotion_genres.get(emotion, ["pop"])
    keyword = random.choice(genres)
    try:
        results = sp.search(q=keyword, type="track", limit=5)
        tracks = results['tracks']['items']
        recommendations = [
            {"name": track['name'], "artist": track['artists'][0]['name'], "url": track['external_urls']['spotify']}
            for track in tracks
        ]
        return keyword, recommendations
    except Exception as e:
        logging.error(f"Error in get_spotify_recommendations: {e}")
        return None, []

# --- Optional: Random writing prompt ---
def get_random_prompt():
    try:
        with open('prompts.txt', 'r') as file:
            prompts = file.readlines()
            return random.choice(prompts).strip()
    except Exception as e:
        logging.error(f"Error reading prompts.txt: {e}")
        return "Write about anything that's on your mind."

# --- Routes ---
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/journal', methods=['GET', 'POST'])
def journal():
    prompt = get_random_prompt()
    if request.method == 'POST':
        entry = request.form['entry']
        user_id = str(uuid.uuid4())

        try:
            emotion = get_emotion_from_text(entry)
            genre, recommendations = get_spotify_recommendations(emotion)

            # Save the mood entry in the database
            mood_entry = MoodEntry(
                user_id=user_id,
                date=datetime.today().date(),
                emotion=emotion,
                journal_entry=entry
            )
            db.session.add(mood_entry)
            db.session.commit()

            return render_template(
                'journal.html',
                emotion=emotion,
                genre=genre,
                recommendations=recommendations,
                entry=entry,
                prompt=prompt
            )
        except Exception as e:
            logging.error(f"Error in /journal route: {e}")
            return "There was an error processing your request.", 500
    return render_template('journal.html', prompt=prompt)

@app.route('/calendar')
def calendar():
    try:
        mood_entries = MoodEntry.query.all()
        return render_template('calendar.html', mood_entries=mood_entries)
    except Exception as e:
        logging.error(f"Error in /calendar route: {e}")
        return "There was an error loading the calendar.", 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5001)
