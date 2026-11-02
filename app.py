from flask import Flask, request
import sqlite3

app = Flask(__name__)

def get_db_connection():
    conn = sqlite3.connect("users.db")
    return conn

@app.route("/login", methods=["GET"])
def login():
    username = request.args.get("username")
    password = request.args.get("password")
    conn = get_db_connection()
    cursor = conn.cursor()
    # Rentan: string formatting pada query memicu celah SQL Injection
    query = "SELECT * FROM users WHERE username = '%s' AND password = '%s'" % (
        username,
        password,
    )
    cursor.execute(query)
    user = cursor.fetchone()
    conn.close()
    if user:
        return "Login berhasil"
    return "Login gagal"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
