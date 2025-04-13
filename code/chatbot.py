import nltk
import re
import os
import pandas as pd
from fuzzywuzzy import fuzz
from fuzzywuzzy import process
from nltk.tokenize import word_tokenize
from nltk.stem import WordNetLemmatizer
from nltk.sentiment import SentimentIntensityAnalyzer
from datetime import datetime
from config import SEPARATE_SESSION_LOGS

# Download necessary NLTK resources
nltk.download('punkt')
nltk.download('wordnet')
nltk.download('vader_lexicon')

lemmatizer = WordNetLemmatizer()
sentiment_analyzer = SentimentIntensityAnalyzer()

# Load FAQ data
faq_data = pd.read_csv("faq_data.csv", on_bad_lines='skip')


# Preprocess input (tokenize + lemmatize)
def preprocess_input(user_input):
    tokens = word_tokenize(user_input.lower())
    lemmatized = [lemmatizer.lemmatize(token) for token in tokens]
    return ' '.join(lemmatized)

# Intent detection using regex & fuzzy matching
# Intent detection using regex & fuzzy matching
def get_intents(user_input, faq_data, threshold=80):
    normalized_input = preprocess_input(user_input)
    best_match = None
    best_score = 0

    for _, row in faq_data.iterrows():
        intent = row['intent']
        patterns = row['patterns'].split('|')

        for pattern in patterns:
            if re.search(rf'\b{re.escape(pattern)}\b', normalized_input, re.IGNORECASE):
                return [intent]  # Exact match, highest priority

            score = fuzz.partial_ratio(pattern.lower(), normalized_input)
            if score > best_score and score >= threshold:
                best_match = intent
                best_score = score

    return [best_match] if best_match else []



# Return the response for an intent
def get_response(intent, faq_data):
    row = faq_data[faq_data['intent'] == intent]
    return row['response'].values[0] if not row.empty else "Hmm... I don't have an answer for that yet."

# Optional sentiment analysis
def analyze_sentiment(text):
    score = sentiment_analyzer.polarity_scores(text)
    if score['compound'] >= 0.5:
        return {"text": "You seem happy!", "emoji": "😊"}
    elif score['compound'] <= -0.5:
        return {"text": "You sound a bit upset. I'm here to help!", "emoji": "😟"}
    return None

# Get log file path
def get_log_file(use_session_log=False):
    log_dir = "logs"
    os.makedirs(log_dir, exist_ok=True)

    if use_session_log:
        now = datetime.now().strftime("%Y%m%d_%H%M%S")
        return os.path.join(log_dir, f"chat_log_{now}.txt")
    return os.path.join(log_dir, "chat_log.txt")


def fuzzy_match_follow_up(user_input, followup_info, threshold=75):
    for keyword, reply in followup_info.get("replies", {}).items():
        if fuzz.partial_ratio(user_input.lower(), keyword.lower()) >= threshold:
            return keyword
    return None

# Optional follow-up messages
follow_up_map = {
    "library": {
        "question": "📚 Would you like help finding a book or knowing the sections?",
        "replies": {
            "book": "You can search for books using the library catalog system.",
            "section": "The reference and fiction sections are on the 1st floor.",
        }
    },
    "canteen": {
        "question": "🍽️ Do you want the full menu or meal timings?",
        "replies": {
            "menu": "You can view the daily menu on the student portal.",
            "timing": "The canteen is open from 8 AM to 8 PM.",
        }
    },
    "admissions": {
    "question": "📝 Are you asking about application deadlines or required documents?",
    "replies": {
        "deadline": "The application deadline is June 30.",
        "documents": "You'll need your transcripts, ID proof, and recommendation letters."
    }
}
}



# Add this at the bottom of chatbot.py
awaiting_followup_intent = None  # Global fallback, but better to pass via argument

def get_bot_response(user_input, session):
    intents = get_intents(user_input, faq_data)
    sentiment = analyze_sentiment(user_input)

    # Handle follow-up intent if waiting
    if session.get("awaiting_followup_intent"):
        followup_intent = session["awaiting_followup_intent"]
        if is_followup_response(user_input):
            response = get_response(followup_intent, faq_data)
            if sentiment:
                response += f" {sentiment['emoji']}"
            session["awaiting_followup_intent"] = None  # reset
            return response, session

    if intents:
        intent = intents[0]
        response = get_response(intent, faq_data)

        # If this intent expects a follow-up
        if intent in ["library", "book"]:
            response += " 📚 Would you like help finding a book or knowing the sections?"
            session["awaiting_followup_intent"] = intent

        if sentiment:
            response += f" {sentiment['emoji']}"
        return response, session

    return "I'm not sure I understand. Can you rephrase?", session



def campus_chatbot(use_session_log=False):
    log_file = get_log_file(use_session_log)
    print("🎓 Welcome to Campus Helpdesk Bot!\nType 'exit' or 'quit' to end the chat.\n")

    with open(log_file, "a", encoding="utf-8") as log:
        log.write("\n" + "="*40 + f"\nNew session started: {datetime.now()}\n" + "="*40 + "\n")

    previous_intent = None
    awaiting_followup_intent = None

    while True:
        user_input = input("You: ").strip()
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        if user_input.lower() in ['exit', 'quit']:
            farewell = "See you! Have a great day at campus! 👋"
            print("Bot:", farewell)
            with open(log_file, "a", encoding="utf-8") as log:
                log.write(f"[{timestamp}] User: {user_input}\n")
                log.write(f"[{timestamp}] Bot: {farewell}\n")
            break

        with open(log_file, "a", encoding="utf-8") as log:
            log.write(f"[{timestamp}] User: {user_input}\n")

        intents = get_intents(user_input, faq_data)
        sentiment = analyze_sentiment(user_input)

        # 💬 Check for follow-up reply if waiting
        '''
        if awaiting_followup_intent:
            # Check if user_input matches any new intent first (break out of follow-up mode)
            new_intents = get_intents(user_input, faq_data)
            if new_intents and new_intents[0] != awaiting_followup_intent:
                awaiting_followup_intent = None
                intents = new_intents  # Override with new intent
            else:
                followup_info = follow_up_map.get(awaiting_followup_intent, {})
                possible_replies = followup_info.get("replies", {})

                matched_key, score = process.extractOne(user_input.lower(), possible_replies.keys())
                if score >= 70:
                    response = possible_replies[matched_key]
                    print("Bot:", response)
                    with open(log_file, "a", encoding="utf-8") as log:
                        log.write(f"[{timestamp}] Bot: {response}\n")
                    awaiting_followup_intent = None
                else:
                    clarification = "Could you clarify your response to my previous question?"
                    print("Bot:", clarification)
                    with open(log_file, "a", encoding="utf-8") as log:
                        log.write(f"[{timestamp}] Bot: {clarification}\n")
                continue
'''
        # ✨ Intent matched
        if intents:
            current_intent = intents[0]

            # Avoid redundant logging
            if current_intent != previous_intent:
                previous_intent = current_intent

            # Get the response for the matched intent
            response = get_response(current_intent, faq_data)

            # Check if the current intent expects a follow-up
            if current_intent in follow_up_map:
                followup_q = follow_up_map[current_intent]["question"]
                print("Bot:", followup_q)

                # Log the follow-up question
                with open(log_file, "a", encoding="utf-8") as log:
                    log.write(f"[{timestamp}] Bot: {followup_q}\n")

                # Set the awaiting follow-up intent
                awaiting_followup_intent = current_intent
                return  # Return early to process follow-up immediately

            # Handle follow-up response if it's waiting
            if awaiting_followup_intent:
                followup_info = follow_up_map.get(awaiting_followup_intent, {})
                possible_replies = followup_info.get("replies", {})

                # Perform fuzzy matching to find the most relevant follow-up reply
                matched_key, score = process.extractOne(user_input.lower(), possible_replies.keys())

                if score >= 70:  # Threshold for fuzzy match (you can adjust this threshold)
                    response = possible_replies[matched_key]
                    print("Bot:", response)

                    # Log the response
                    with open(log_file, "a", encoding="utf-8") as log:
                        log.write(f"[{timestamp}] Bot: {response}\n")

                    # Reset follow-up intent after processing
                    awaiting_followup_intent = None
                    return  # Exit after handling follow-up

                else:
                    clarification = "Could you clarify your response to my previous question?"
                    print("Bot:", clarification)
                    with open(log_file, "a", encoding="utf-8") as log:
                        log.write(f"[{timestamp}] Bot: {clarification}\n")
                    return  # Exit until clarification is made

            # If no follow-up is required, continue with the normal response
            if sentiment:
                response += f" {sentiment['emoji']}"

            # Print the bot's response
            print("Bot:", response)

            # Log the bot's response
            with open(log_file, "a", encoding="utf-8") as log:
                log.write(f"[{timestamp}] Bot: {response}\n")
                if sentiment:
                    log.write(f"[{timestamp}] Bot: {sentiment['text']}\n")


            # 💬 Follow-up question trigger
            if current_intent in follow_up_map:
                followup_q = follow_up_map[current_intent]["question"]
                print("Bot:", followup_q)
                awaiting_followup_intent = current_intent

                with open(log_file, "a", encoding="utf-8") as log:
                    log.write(f"[{timestamp}] Bot: {followup_q}\n")

        else:
            fallback = "I'm sorry, I didn't quite get that. Could you please rephrase?"
            print("Bot:", fallback)
            with open(log_file, "a", encoding="utf-8") as log:
                log.write(f"[{timestamp}] Bot: {fallback}\n")

# Entry point
if __name__ == "__main__":
    campus_chatbot(use_session_log=SEPARATE_SESSION_LOGS)
