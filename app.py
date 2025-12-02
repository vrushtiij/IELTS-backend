from flask import Flask, request, jsonify , session
from flask_cors import CORS
import mysql.connector
from werkzeug.security import generate_password_hash, check_password_hash
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity
from datetime import timedelta

app = Flask(__name__)
CORS(app)

app.config['JWT_SECRET_KEY'] = 'secret-key'  
app.config['JWT_ACCESS_TOKEN_EXPIRES'] = timedelta(hours=1)
jwt = JWTManager(app)

db = mysql.connector.connect(
    host="sql12.freesqldatabase.com",
    user="sql12810293",
    password=" nGIR7sjw86",  
    database="sql12810293"
)
cursor = db.cursor()

def calculate_band_score(scaled):
    if scaled >= 39:
        return 9.0
    elif scaled >= 37:
        return 8.5
    elif scaled >= 35:
        return 8.0
    elif scaled >= 33:
        return 7.5
    elif scaled >= 30:
        return 7.0
    elif scaled >= 27:
        return 6.5
    elif scaled >= 23:
        return 6.0
    elif scaled >= 19:
        return 5.5
    elif scaled >= 15:
        return 5.0
    elif scaled >= 13:
        return 4.5
    elif scaled >= 10:
        return 4.0
    elif scaled >= 8:
        return 3.5
    elif scaled >= 6:
        return 3.0
    elif scaled >= 4:
        return 2.5
    elif scaled >= 3:
        return 2.0
    elif scaled >= 2:
        return 1.5
    elif scaled >= 1:
        return 1.0
    else:
        return 0


@app.route("/login", methods=["POST"])
def login():
    data = request.get_json()
    email = data.get("email")
    password = data.get("password")

    cursor.execute("SELECT user_id, password FROM login WHERE email=%s", (email,))
    result = cursor.fetchone()

    if result and check_password_hash(result[1], password):   
        access_token = create_access_token(identity=email)
        return jsonify({
            "success": True,
            "message": "Login successful!",
            "access_token": access_token
        }), 200
    else:
        return jsonify({
            "success": False,
            "message": "Invalid credentials."
        }), 401

@app.route("/signup", methods=["POST"])
def signup():
    data = request.get_json()
    name = data.get("uname")
    email = data.get("email")
    password = data.get("password")
    password = generate_password_hash(password)
    
    try:
        check_query = "SELECT * FROM login WHERE email=%s"
        cursor.execute(check_query, (email,))
        if cursor.fetchone():
            return jsonify({"success": False, "message": "Email already exists"}), 400
            
        
        insert_query = "INSERT INTO login (email, password, name) VALUES (%s, %s, %s)"
        cursor.execute(insert_query, (email, password, name))
        db.commit()
        
        return jsonify({"success": True, "message": "Signup successful!"})
    except Exception as e:
        db.rollback()
        return jsonify({"success": False, "message": str(e)}), 500

@app.route("/landing", methods=["GET"])
@jwt_required()
def get_user_name():
    user_email = get_jwt_identity()
    cursor.execute("SELECT name FROM login WHERE email = %s", (user_email,))
    userName = cursor.fetchone()[0]

    return jsonify({"success": True, "userName": userName})


@app.route("/reading-test", methods=["GET"])
def get_reading_test():
    cursor.execute("SELECT passage_id, title, content FROM passages")
    passages = cursor.fetchall()

    passage_list = [
        {
            "passage_id": p[0],
            "title": p[1],
            "content": p[2]
        }
        for p in passages
    ]

    cursor.execute("""
        SELECT question_id, passage_id, question_text, question_type, correct_answer 
        FROM questions
    """)
    questions = cursor.fetchall()

    question_list = [
        {
            "question_id": q[0],
            "passage_id": q[1],
            "question_text": q[2],
            "question_type": q[3],
            "correct_answer": q[4]
        }
        for q in questions
    ]

    cursor.execute("SELECT option_id, question_id, option_label, option_text FROM options")
    options = cursor.fetchall()

    option_list = [
        {
            "option_id": o[0],
            "question_id": o[1],
            "option_label": o[2],
            "option_text": o[3]
        }
        for o in options
    ]

    return jsonify({
        "passages": passage_list,
        "questions": question_list,
        "options": option_list
    })

@app.route("/submit-reading-test", methods=["POST"])
@jwt_required()
def submit_reading_test():
    user_email = get_jwt_identity()
    
    cursor.execute("SELECT user_id FROM login WHERE email=%s", (user_email,))
    user_id = cursor.fetchone()[0]

    answers = request.json.get("answers")
    print("Received answers:", answers)

    for qid_str, user_answer in answers.items():
        qid = int(qid_str)

        cursor.execute(
            "SELECT correct_answer FROM questions WHERE question_id=%s",
            (qid,)
        )
        correct_answer_row = cursor.fetchone()

        if not correct_answer_row:
            print("Question NOT FOUND:", qid)
            continue

        correct_answer = correct_answer_row[0]

        is_correct = (user_answer.strip().lower() == correct_answer.strip().lower())

        cursor.execute("""
            INSERT INTO user_answers (user_id, question_id, user_answer, is_correct)
            VALUES (%s, %s, %s, %s)
        """, (user_id, qid, user_answer, is_correct))


    db.commit()
    return jsonify({"success": True})


@app.route("/get-reading-result", methods=["GET"])
@jwt_required()
def get_reading_result():
    user_email = get_jwt_identity()

    cursor.execute("SELECT user_id FROM login WHERE email=%s", (user_email,))
    user_id = cursor.fetchone()[0]

    cursor.execute("""
            SELECT q.question_id, q.correct_answer, ua.user_answer, q.passage_id
            FROM user_answers ua
            JOIN questions q ON ua.question_id = q.question_id
            WHERE ua.user_id = %s
            AND ua.timestamp = (
            SELECT MAX(timestamp)
            FROM user_answers
            WHERE user_id = %s
        );

    """, (user_id, user_id))
    rows = cursor.fetchall()
    print("DEBUG rows:", rows)

    if not rows:
        return jsonify({"error": "No attempts found"}), 404

    correct = 0
    passage_data = {}

    for qid, correct_ans, user_ans, passage_id in rows:
        if passage_id not in passage_data:
            passage_data[passage_id] = {"correct": 0, "total": 0}

        passage_data[passage_id]["total"] += 1

        if user_ans and correct_ans and user_ans.strip().lower() == correct_ans.strip().lower():
            correct += 1
            passage_data[passage_id]["correct"] += 1

    total = len(rows)
    scaled = (correct / total) * 40 if total > 0 else 0
    band = calculate_band_score(scaled)

    passage_breakdown = [
        {"passage": p, "correct": data["correct"], "total": data["total"]}
        for p, data in sorted(passage_data.items())
    ]

    return jsonify({
        "band_score": band,
        "correct": correct,
        "total": total,
        "accuracy": round((correct/total)*100) if total > 0 else 0,
        "time_taken": "—",
        "passage_breakdown": passage_breakdown
    })

if __name__ == "__main__":
    app.run(debug=True, port=5000)