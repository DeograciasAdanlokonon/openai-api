# api.py
from flask import Flask, request, jsonify, render_template
from dotenv import load_dotenv
from openai import OpenAI
import os
import sqlite3
import logging
import threading

# Load environment variables
# load_dotenv()

app = Flask(__name__)

# Configure OpenAI client
client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

# Database setup
conn = sqlite3.connect('competences.db', check_same_thread=False)
c = conn.cursor()

# Create competences table if it doesn't exist
c.execute('''CREATE TABLE IF NOT EXISTS competences (prompt TEXT, response TEXT)''')
conn.commit()

# Logging setup
logging.basicConfig(filename='assistant.log', level=logging.INFO, format='%(asctime)s:%(levelname)s:%(message)s')


def async_get_response(prompt, result_container):
    try:
        response = client.chat.completions.create(
            model="gpt-4-turbo",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=150
        )
        reply = response.choices[0].message.content.strip()
        result_container["data"] = reply
    except Exception as e:
        result_container["data"] = str(e)


@app.route('/')
def home():
    return render_template('index.html')


@app.route('/get_response', methods=['POST'])
def get_response():
    prompt = request.json.get("prompt")
    c.execute("SELECT response FROM competences WHERE prompt=?", (prompt,))
    result = c.fetchone()
    if result:
        return jsonify({"response": result[0]})

    response_container = {"data": None}

    thread = threading.Thread(target=async_get_response, args=(prompt, response_container))
    thread.start()
    thread.join()

    if response_container["data"]:
        c.execute("INSERT INTO competences (prompt, response) VALUES (?, ?)", (prompt, response_container["data"]))
        conn.commit()
        return jsonify({"response": response_container["data"]})
    else:
        return jsonify({"error": "Failed to retrieve response"}), 500


@app.route('/learn', methods=['POST'])
def learn():
    prompt = request.json.get("prompt")
    expected_response = request.json.get("expected_response")
    try:
        # Insert prompt and expected response into the database
        c.execute("INSERT INTO competences (prompt, response) VALUES (?, ?)", (prompt, expected_response))
        conn.commit()
        logging.info(f"Learned new competence: {prompt} -> {expected_response}")
        return jsonify({"message": "New competence added successfully!"})
    except Exception as e:
        logging.error(f"Database error: {e}")
        return jsonify({"error": str(e)})


if __name__ == "__main__":
    # run app in debug mode to auto-load our server
    app.run(debug=True, host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))
