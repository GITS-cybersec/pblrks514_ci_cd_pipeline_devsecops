"""Aplikasi Flask: registrasi, login berbasis sesi, dan dashboard (MySQL)."""

import os
import re
import time
from contextlib import contextmanager
from functools import wraps

import pymysql
from dotenv import load_dotenv
from flask import (
    Flask,
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from flask_wtf.csrf import CSRFError, CSRFProtect
from werkzeug.security import check_password_hash, generate_password_hash

# Membaca file .env saat pengembangan lokal. Di Docker/CI variabel
# lingkungan sudah diberikan langsung, sehingga baris ini tidak berpengaruh.
load_dotenv()


def require_env(name):
    """Mengambil variabel lingkungan wajib; gagal cepat jika belum diatur."""
    value = os.getenv(name)
    if not value:
        raise RuntimeError(
            f"Variabel lingkungan {name} belum diatur (lihat .env.example)"
        )
    return value


app = Flask(__name__)
app.config.update(
    SECRET_KEY=require_env("SECRET_KEY"),
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=os.getenv("COOKIE_SECURE", "false").lower() == "true",
)
csrf = CSRFProtect(app)

DB_CONFIG = {
    "host": require_env("DB_HOST"),
    "port": int(os.getenv("DB_PORT", "3306")),
    "user": require_env("DB_USER"),
    "password": require_env("DB_PASSWORD"),
    "database": require_env("DB_NAME"),
}

USERNAME_RE = re.compile(r"^[A-Za-z0-9_]{3,30}$")
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
# Hash palsu agar waktu respons sama baik pengguna ada maupun tidak ada.
DUMMY_HASH = generate_password_hash("kata-sandi-palsu")

CREATE_USERS_TABLE = """
CREATE TABLE IF NOT EXISTS users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(30) NOT NULL UNIQUE,
    email VARCHAR(120) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
) CHARACTER SET utf8mb4
"""


@contextmanager
def db_cursor(commit=False):
    """Membuka koneksi MySQL, memberi cursor, lalu menutupnya dengan rapi."""
    conn = pymysql.connect(
        **DB_CONFIG,
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
        connect_timeout=5,
    )
    try:
        with conn.cursor() as cursor:
            yield cursor
        if commit:
            conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db(retries=5, delay=2):
    """Membuat tabel users; mencoba ulang bila MySQL belum siap."""
    for attempt in range(1, retries + 1):
        try:
            with db_cursor(commit=True) as cursor:
                cursor.execute(CREATE_USERS_TABLE)
            return
        except pymysql.MySQLError as exc:
            if attempt == retries:
                raise
            app.logger.warning(
                "MySQL belum siap (%s/%s): %s", attempt, retries, exc
            )
            time.sleep(delay)


def login_required(view):
    """Dekorator: hanya pengguna yang sudah login yang boleh mengakses."""

    @wraps(view)
    def wrapped(*args, **kwargs):
        if "user_id" not in session:
            flash("Silakan login terlebih dahulu.", "warning")
            return redirect(url_for("index"))
        return view(*args, **kwargs)

    return wrapped


@app.after_request
def add_no_store_header(response):
    """Cegah halaman privat tampil dari cache browser setelah logout."""
    if "user_id" in session:
        response.headers["Cache-Control"] = "no-store"
    return response


def validate_registration(username, email, password, confirm):
    """Mengembalikan daftar pesan galat validasi formulir registrasi."""
    errors = []
    if not USERNAME_RE.match(username):
        errors.append(
            "Nama pengguna 3-30 karakter: huruf, angka, atau garis bawah."
        )
    if len(email) > 120 or not EMAIL_RE.match(email):
        errors.append("Format email tidak valid.")
    if not 8 <= len(password) <= 128:
        errors.append("Kata sandi harus 8-128 karakter.")
    if password != confirm:
        errors.append("Konfirmasi kata sandi tidak cocok.")
    return errors


@app.route("/", methods=["GET", "POST"])
def index():
    """Menampilkan formulir login dan memproses autentikasi."""
    if "user_id" in session:
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        with db_cursor() as cursor:
            cursor.execute(
                "SELECT id, password_hash FROM users WHERE username = %s",
                (username,),
            )
            user = cursor.fetchone()

        stored_hash = user["password_hash"] if user else DUMMY_HASH
        if check_password_hash(stored_hash, password) and user:
            session.clear()
            session["user_id"] = user["id"]
            return redirect(url_for("dashboard"))

        flash("Login Gagal! Kredensial tidak valid.", "danger")
        return render_template("index.html", username=username), 401

    return render_template("index.html", username="")


@app.route("/register", methods=["GET", "POST"])
def register():
    """Menampilkan formulir pendaftaran dan membuat akun baru."""
    if "user_id" in session:
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        confirm = request.form.get("confirm_password", "")

        errors = validate_registration(username, email, password, confirm)
        if not errors:
            try:
                with db_cursor(commit=True) as cursor:
                    cursor.execute(
                        "INSERT INTO users (username, email, password_hash) "
                        "VALUES (%s, %s, %s)",
                        (username, email, generate_password_hash(password)),
                    )
            except pymysql.err.IntegrityError:
                errors.append("Nama pengguna atau email sudah terdaftar.")
            else:
                flash("Registrasi berhasil! Silakan login.", "success")
                return redirect(url_for("index"))

        for error in errors:
            flash(error, "danger")
        return (
            render_template("register.html", username=username, email=email),
            400,
        )

    return render_template("register.html", username="", email="")


@app.route("/dashboard")
@login_required
def dashboard():
    """Halaman utama pengguna setelah login."""
    with db_cursor() as cursor:
        cursor.execute(
            "SELECT username, email, created_at FROM users WHERE id = %s",
            (session["user_id"],),
        )
        user = cursor.fetchone()

    if not user:
        session.clear()
        flash("Akun tidak ditemukan. Silakan login ulang.", "warning")
        return redirect(url_for("index"))

    return render_template("dashboard.html", user=user)


@app.route("/logout", methods=["POST"])
def logout():
    """Menghapus sesi pengguna (POST + CSRF agar tidak bisa dipicu link)."""
    session.clear()
    flash("Anda sudah keluar.", "success")
    return redirect(url_for("index"))


@app.errorhandler(CSRFError)
def handle_csrf_error(_error):
    """Formulir kedaluwarsa atau token CSRF tidak valid."""
    flash("Formulir kedaluwarsa. Silakan coba lagi.", "warning")
    return redirect(url_for("index"))


@app.errorhandler(pymysql.MySQLError)
def handle_db_error(error):
    """Basis data tidak dapat dijangkau atau query gagal."""
    app.logger.error("Kesalahan basis data: %s", error)
    return "Layanan basis data sedang tidak tersedia. Coba lagi nanti.", 503


init_db()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)  # nosemgrep
