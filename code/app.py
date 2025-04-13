from flask import Flask, render_template, request, jsonify, session, send_file
from flask_session import Session
import os
import datetime
from chatbot import get_bot_response
from io import BytesIO
from fpdf import FPDF

app = Flask(__name__)
app.secret_key = "chat-secret"

# Enable server-side sessions
app.config['SESSION_TYPE'] = 'filesystem'
Session(app)

# Define log file path
LOG_DIR = 'logs'
if not os.path.exists(LOG_DIR):
    os.makedirs(LOG_DIR)

LOG_FILE_PATH = os.path.join(LOG_DIR, 'chat_log.txt')

@app.route('/')
def index():
    session.clear()
    return render_template('index.html')

@app.route('/chat', methods=['POST'])
def chat():
    user_msg = request.json['message']

    if "chat_session" not in session:
        session["chat_session"] = {}

    reply, updated_session = get_bot_response(user_msg, session["chat_session"])
    session["chat_session"] = updated_session

    # Save the conversation to log
    save_log(user_msg, reply)

    return jsonify({'reply': reply})

# Save the log to a file
def save_log(user_message, bot_response):
    timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    with open(LOG_FILE_PATH, 'a') as log_file:
        log_file.write(f"[{timestamp}] User: {user_message}\n")
        log_file.write(f"[{timestamp}] Bot: {bot_response}\n")

# View chat log
@app.route('/view_log', methods=['GET'])
def view_log():
    try:
        with open(LOG_FILE_PATH, 'r') as log_file:
            logs = log_file.read()
        return jsonify({'logs': logs})
    except FileNotFoundError:
        return jsonify({'error': 'Log file not found'})

# Clear chat history
@app.route('/clear_chat', methods=['POST'])
def clear_chat():
    open(LOG_FILE_PATH, 'w').close()  # Clear log file
    return jsonify({'message': 'Chat history cleared successfully'})

# Export chat to PDF
@app.route('/export_chat_pdf', methods=['GET'])
def export_chat_pdf():
    try:
        # Create a PDF object
        pdf = FPDF()
        pdf.set_auto_page_break(auto=True, margin=15)
        pdf.add_page()
        pdf.set_font("Arial", size=12)

        # Read chat logs and add to PDF
        with open(LOG_FILE_PATH, 'r') as log_file:
            logs = log_file.readlines()

        for line in logs:
            pdf.multi_cell(0, 10, line)

        # Create a byte stream to send as a response
        pdf_output = BytesIO()
        pdf.output(pdf_output)
        pdf_output.seek(0)

        # Send the PDF file to the client
        return send_file(pdf_output, as_attachment=True, download_name="chat_log.pdf", mimetype='application/pdf')

    except FileNotFoundError:
        return jsonify({'error': 'Log file not found'})

if __name__ == "__main__":
    app.run(debug=True)
