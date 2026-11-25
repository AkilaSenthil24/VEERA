import hmac
import os
import re
import secrets
import sqlite3
import uuid
from functools import wraps
from urllib.parse import urlparse

from flask import (
    Flask,
    abort,
    flash,
    g,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from werkzeug.middleware.proxy_fix import ProxyFix
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "database.db")
UPLOAD_DIR = os.path.join(BASE_DIR, "static", "uploads")
ALLOWED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".gif"}

CATEGORIES = [
    "Electronics",
    "Bags & Backpacks",
    "Keys & ID Cards",
    "Books & Notes",
    "Drinkware & Gear",
    "Clothing & Accessories",
    "Other",
]

CAMPUS_LOCATIONS = [
    "Main Library",
    "Student Union",
    "Science Quad",
    "Engineering Hall",
    "Recreation Center",
    "Mathematics Building",
    "Dining Commons",
    "North Residence Hall",
    "Campus Transit Stop",
]

DEPARTMENTS = [
    "Computer Science",
    "Electrical Engineering",
    "Mechanical Engineering",
    "Mathematics",
    "Biological Sciences",
    "Business Administration",
    "Psychology",
    "Architecture & Design",
    "Economics",
    "Faculty / Staff",
]

STUDY_YEARS = [
    "1st Year",
    "2nd Year",
    "3rd Year",
    "4th Year",
    "Graduate",
    "Faculty / Staff",
]

app = Flask(__name__)
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)
app.secret_key = os.environ.get("FLASK_SECRET_KEY") or secrets.token_hex(32)
app.config["MAX_CONTENT_LENGTH"] = 5 * 1024 * 1024  # 5 MB upload limit
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_NAME"] = "findback_session"

os.makedirs(UPLOAD_DIR, exist_ok=True)


def get_db():
    if "db" not in g:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        g.db = conn
    return g.db


@app.teardown_appcontext
def close_db(exception=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    cur = conn.cursor()

    cur.executescript(
        """
        CREATE TABLE IF NOT EXISTS Users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            full_name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            student_id TEXT NOT NULL,
            department TEXT NOT NULL,
            year TEXT NOT NULL,
            phone TEXT NOT NULL,
            password_hash TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS Items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            item_name TEXT NOT NULL,
            category TEXT NOT NULL,
            description TEXT NOT NULL,
            location TEXT NOT NULL,
            item_date TEXT NOT NULL,
            contact_info TEXT NOT NULL DEFAULT '',
            image TEXT DEFAULT '',
            item_type TEXT NOT NULL CHECK(item_type IN ('Lost', 'Found')),
            status TEXT NOT NULL DEFAULT 'Active',
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (user_id) REFERENCES Users(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS Claims (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            item_id INTEGER NOT NULL,
            claimant_id INTEGER NOT NULL,
            claimant_name TEXT NOT NULL,
            student_id TEXT NOT NULL,
            claim_description TEXT NOT NULL,
            identifying_details TEXT NOT NULL,
            contact_number TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'Pending' CHECK(status IN ('Pending', 'Approved', 'Rejected')),
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (item_id) REFERENCES Items(id) ON DELETE CASCADE,
            FOREIGN KEY (claimant_id) REFERENCES Users(id) ON DELETE CASCADE
        );
        """
    )

    user_count = cur.execute("SELECT COUNT(*) FROM Users").fetchone()[0]
    if user_count == 0:
        demo_users = [
            (
                "Maya Patel",
                "maya.patel@campus.edu",
                "STU-2026-1042",
                "Computer Science",
                "3rd Year",
                "(555) 234-8810",
                generate_password_hash(secrets.token_urlsafe(24)),
            ),
            (
                "Daniel Kim",
                "daniel.kim@campus.edu",
                "STU-2026-2189",
                "Mechanical Engineering",
                "2nd Year",
                "(555) 391-4420",
                generate_password_hash(secrets.token_urlsafe(24)),
            ),
            (
                "Elena Ross",
                "elena.ross@campus.edu",
                "STU-2026-0874",
                "Mathematics",
                "4th Year",
                "(555) 612-7731",
                generate_password_hash(secrets.token_urlsafe(24)),
            ),
        ]
        cur.executemany(
            """
            INSERT INTO Users (full_name, email, student_id, department, year, phone, password_hash)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            demo_users,
        )

        maya_id = cur.execute(
            "SELECT id FROM Users WHERE email = ?", ("maya.patel@campus.edu",)
        ).fetchone()[0]
        daniel_id = cur.execute(
            "SELECT id FROM Users WHERE email = ?", ("daniel.kim@campus.edu",)
        ).fetchone()[0]
        elena_id = cur.execute(
            "SELECT id FROM Users WHERE email = ?", ("elena.ross@campus.edu",)
        ).fetchone()[0]

        sample_items = [
            (
                maya_id,
                "Matte Black Wireless Headphones",
                "Electronics",
                "Over-ear noise-canceling headphones left on a study carrel desk on the second floor quiet wing of Main Library. No case attached.",
                "Main Library",
                "2026-11-22",
                "maya.patel@campus.edu · Library Front Desk",
                "samples/item_headphones.jpg",
                "Found",
                "Active",
                "2026-11-22 14:20:00",
            ),
            (
                daniel_id,
                "Navy Canvas Backpack with Tan Trim",
                "Bags & Backpacks",
                "Dark navy canvas daypack with tan leather zipper pulls and a silver thermos in the side pocket. Last seen near the limestone benches outside Science Quad.",
                "Science Quad",
                "2026-11-21",
                "daniel.kim@campus.edu · (555) 391-4420",
                "samples/item_backpack.jpg",
                "Lost",
                "Active",
                "2026-11-21 17:05:00",
            ),
            (
                elena_id,
                "Cobalt Insulated Water Bottle",
                "Drinkware & Gear",
                "32 oz matte cobalt blue stainless steel bottle with a black chug cap. Found on the counter near the Student Union espresso bar.",
                "Student Union",
                "2026-11-23",
                "elena.ross@campus.edu · Student Union Info Desk",
                "samples/item_bottle.jpg",
                "Found",
                "Active",
                "2026-11-23 11:40:00",
            ),
            (
                maya_id,
                "Scientific Graphing Calculator",
                "Electronics",
                "Black TI-84 style graphing calculator left behind after the 10:00 AM Differential Equations lecture in Engineering Hall Room 204.",
                "Engineering Hall",
                "2026-11-20",
                "maya.patel@campus.edu · (555) 234-8810",
                "samples/item_calculator.jpg",
                "Lost",
                "Active",
                "2026-11-20 12:15:00",
            ),
            (
                daniel_id,
                "Dorm & Bike Keys on Indigo Lanyard",
                "Keys & ID Cards",
                "Two brass keys stamped B-231 and a circular silver anchor fob attached to a woven indigo-purple lanyard. Found near the Recreation Center lockers.",
                "Recreation Center",
                "2026-11-23",
                "daniel.kim@campus.edu · Rec Center Front Desk",
                "samples/item_keys.jpg",
                "Found",
                "Pending Claim",
                "2026-11-23 16:50:00",
            ),
            (
                elena_id,
                "Linear Algebra Hardcover Textbook",
                "Books & Notes",
                "Hardcover textbook with blue sticky tabs on Chapter 4 and handwritten margin notes. Found in the Mathematics Building atrium and returned to owner.",
                "Mathematics Building",
                "2026-11-18",
                "elena.ross@campus.edu",
                "",
                "Found",
                "Returned",
                "2026-11-18 09:30:00",
            ),
        ]
        cur.executemany(
            """
            INSERT INTO Items (
                user_id, item_name, category, description, location,
                item_date, contact_info, image, item_type, status, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            sample_items,
        )

        keys_item_id = cur.execute(
            "SELECT id FROM Items WHERE item_name = ?",
            ("Dorm & Bike Keys on Indigo Lanyard",),
        ).fetchone()[0]
        cur.execute(
            """
            INSERT INTO Claims (
                item_id, claimant_id, claimant_name, student_id,
                claim_description, identifying_details, contact_number, status
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, 'Pending')
            """,
            (
                keys_item_id,
                elena_id,
                "Elena Ross",
                "STU-2026-0874",
                "These are my North Hall room key and U-lock bike key on my campus lanyard.",
                "Silver medallion has 'Voyager Est. 1928' engraving on the front face.",
                "(555) 612-7731",
            ),
        )

    conn.commit()
    conn.close()


def get_csrf_token():
    token = session.get("_csrf_token")
    if not token:
        token = secrets.token_urlsafe(32)
        session["_csrf_token"] = token
    return token


@app.before_request
def csrf_protect():
    if request.method in ("POST", "PUT", "PATCH", "DELETE"):
        session_token = session.get("_csrf_token", "")
        form_token = request.form.get("csrf_token") or request.headers.get("X-CSRF-Token", "")
        if not session_token or not form_token or not hmac.compare_digest(session_token, form_token):
            flash("Your session form token expired. Please try submitting again.", "error")
            return redirect(request.referrer or url_for("index"))


@app.after_request
def adjust_session_cookie(response):
    is_https = (
        request.is_secure
        or request.headers.get("X-Forwarded-Proto", "").lower() == "https"
        or os.environ.get("APP_URL", "").startswith("https://")
    )
    if is_https:
        cookies = response.headers.getlist("Set-Cookie")
        updated = []
        changed = False
        for cookie in cookies:
            if cookie.startswith(f"{app.config['SESSION_COOKIE_NAME']}="):
                changed = True
                cookie = re.sub(r";\s*SameSite=\w+", "", cookie, flags=re.IGNORECASE)
                if "Secure" not in cookie:
                    cookie += "; Secure"
                cookie += "; SameSite=None; Partitioned"
            updated.append(cookie)
        if changed:
            del response.headers["Set-Cookie"]
            for cookie in updated:
                response.headers.add("Set-Cookie", cookie)
    return response


@app.context_processor
def inject_globals():
    user = None
    user_id = session.get("user_id")
    if user_id:
        db = get_db()
        row = db.execute(
            "SELECT id, full_name, email, student_id, department, year, phone, created_at FROM Users WHERE id = ?",
            (user_id,),
        ).fetchone()
        if row:
            user = dict(row)
        else:
            session.pop("user_id", None)
    return {
        "current_user": user,
        "csrf_token": get_csrf_token,
        "categories": CATEGORIES,
        "campus_locations": CAMPUS_LOCATIONS,
        "departments": DEPARTMENTS,
        "study_years": STUDY_YEARS,
    }


def login_required(view):
    @wraps(view)
    def wrapped_view(*args, **kwargs):
        if not session.get("user_id"):
            flash("Please sign in with your campus account to continue.", "warning")
            return redirect(url_for("login", next=request.path))
        return view(*args, **kwargs)

    return wrapped_view


def is_safe_redirect_url(target):
    if not target:
        return False
    parsed = urlparse(target)
    return not parsed.netloc and not parsed.scheme and target.startswith("/") and not target.startswith("//")


def is_valid_image_header(header):
    if header.startswith(b"\x89PNG\r\n\x1a\n"):
        return True
    if header.startswith(b"\xff\xd8\xff"):
        return True
    if header.startswith(b"GIF87a") or header.startswith(b"GIF89a"):
        return True
    if len(header) >= 12 and header[:4] == b"RIFF" and header[8:12] == b"WEBP":
        return True
    return False


def save_uploaded_image(file_storage):
    if not file_storage or not file_storage.filename:
        return "", None

    cleaned_name = secure_filename(file_storage.filename)
    _, ext = os.path.splitext(cleaned_name.lower())
    if ext not in ALLOWED_EXTENSIONS:
        return None, "Invalid image format. Please upload PNG, JPG, JPEG, WEBP, or GIF."

    header = file_storage.stream.read(16)
    file_storage.stream.seek(0)
    if not is_valid_image_header(header):
        return None, "The uploaded file does not appear to be a valid image."

    filename = f"{uuid.uuid4().hex}{ext}"
    dest_path = os.path.realpath(os.path.join(UPLOAD_DIR, filename))
    base_upload = os.path.realpath(UPLOAD_DIR)
    if not dest_path.startswith(base_upload + os.sep):
        return None, "Invalid upload path."

    file_storage.save(dest_path)
    return f"uploads/{filename}", None


def remove_uploaded_image(image_rel_path):
    if not image_rel_path or not image_rel_path.startswith("uploads/"):
        return
    filename = image_rel_path.split("/", 1)[1]
    target = os.path.realpath(os.path.join(UPLOAD_DIR, filename))
    base_upload = os.path.realpath(UPLOAD_DIR)
    if target.startswith(base_upload + os.sep) and os.path.isfile(target):
        os.remove(target)


@app.errorhandler(413)
def file_too_large(e):
    flash("Image file is too large. Maximum allowed size is 5 MB.", "error")
    return redirect(request.referrer or url_for("index"))


@app.route("/health")
def health():
    return {"status": "ok"}, 200


@app.route("/")
def index():
    db = get_db()
    total_lost = db.execute("SELECT COUNT(*) FROM Items WHERE item_type = 'Lost'").fetchone()[0]
    total_found = db.execute("SELECT COUNT(*) FROM Items WHERE item_type = 'Found'").fetchone()[0]
    total_returned = db.execute("SELECT COUNT(*) FROM Items WHERE status = 'Returned'").fetchone()[0]

    recent_items = db.execute(
        """
        SELECT Items.*, Users.full_name AS reporter_name, Users.department AS reporter_department
        FROM Items
        JOIN Users ON Items.user_id = Users.id
        ORDER BY Items.created_at DESC, Items.id DESC
        LIMIT 6
        """
    ).fetchall()

    return render_template(
        "index.html",
        total_lost=total_lost,
        total_found=total_found,
        total_returned=total_returned,
        recent_items=recent_items,
    )


@app.route("/register", methods=["GET", "POST"])
def register():
    if session.get("user_id"):
        return redirect(url_for("dashboard"))

    form_data = {}
    if request.method == "POST":
        full_name = request.form.get("full_name", "").strip()
        email = request.form.get("email", "").strip().lower()
        student_id = request.form.get("student_id", "").strip()
        department = request.form.get("department", "").strip()
        year = request.form.get("year", "").strip()
        phone = request.form.get("phone", "").strip()
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")

        form_data = {
            "full_name": full_name,
            "email": email,
            "student_id": student_id,
            "department": department,
            "year": year,
            "phone": phone,
        }

        errors = []
        if len(full_name) < 2:
            errors.append("Please enter your full name.")
        if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email):
            errors.append("Please enter a valid college email address.")
        if len(student_id) < 3:
            errors.append("Please enter a valid Student / Faculty ID.")
        if not department:
            errors.append("Please select your department.")
        if year not in STUDY_YEARS:
            errors.append("Please select your year of study.")
        if len(re.sub(r"\D", "", phone)) < 7:
            errors.append("Please enter a valid phone number.")
        if len(password) < 8:
            errors.append("Password must be at least 8 characters long.")
        if password != confirm_password:
            errors.append("Passwords do not match.")

        db = get_db()
        if not errors:
            existing = db.execute("SELECT id FROM Users WHERE LOWER(email) = ?", (email,)).fetchone()
            if existing:
                errors.append("An account with this college email address is already registered.")

        if errors:
            for err in errors:
                flash(err, "error")
            return render_template("register.html", form_data=form_data)

        password_hash = generate_password_hash(password)
        db.execute(
            """
            INSERT INTO Users (full_name, email, student_id, department, year, phone, password_hash)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (full_name, email, student_id, department, year, phone, password_hash),
        )
        db.commit()

        flash("Account created successfully! Please sign in with your college email.", "success")
        return redirect(url_for("login"))

    return render_template("register.html", form_data=form_data)


@app.route("/login", methods=["GET", "POST"])
def login():
    if session.get("user_id"):
        return redirect(url_for("dashboard"))

    next_url = request.args.get("next") or request.form.get("next") or ""
    email_prefill = ""

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        email_prefill = email

        if not email or not password:
            flash("Please enter both your college email and password.", "error")
            return render_template("login.html", email_prefill=email_prefill, next_url=next_url)

        db = get_db()
        user = db.execute("SELECT * FROM Users WHERE LOWER(email) = ?", (email,)).fetchone()
        if not user or not check_password_hash(user["password_hash"], password):
            flash("Invalid college email or password.", "error")
            return render_template("login.html", email_prefill=email_prefill, next_url=next_url)

        session["user_id"] = user["id"]
        session["user_name"] = user["full_name"]
        flash(f"Welcome back, {user['full_name']}!", "success")

        if is_safe_redirect_url(next_url):
            return redirect(next_url)
        return redirect(url_for("dashboard"))

    return render_template("login.html", email_prefill=email_prefill, next_url=next_url)


@app.route("/logout", methods=["POST"])
def logout():
    session.pop("user_id", None)
    session.pop("user_name", None)
    flash("You have been signed out.", "info")
    return redirect(url_for("index"))


@app.route("/dashboard")
@login_required
def dashboard():
    db = get_db()
    uid = session["user_id"]

    total_reported = db.execute(
        "SELECT COUNT(*) FROM Items WHERE user_id = ?", (uid,)
    ).fetchone()[0]
    lost_count = db.execute(
        "SELECT COUNT(*) FROM Items WHERE user_id = ? AND item_type = 'Lost'", (uid,)
    ).fetchone()[0]
    found_count = db.execute(
        "SELECT COUNT(*) FROM Items WHERE user_id = ? AND item_type = 'Found'", (uid,)
    ).fetchone()[0]
    successful_claims = db.execute(
        """
        SELECT COUNT(*) FROM Claims
        WHERE (claimant_id = ? AND status = 'Approved')
           OR item_id IN (SELECT id FROM Items WHERE user_id = ? AND status = 'Returned')
        """,
        (uid, uid),
    ).fetchone()[0]

    my_items = db.execute(
        """
        SELECT Items.*,
               (SELECT COUNT(*) FROM Claims WHERE Claims.item_id = Items.id AND Claims.status = 'Pending') AS pending_claims
        FROM Items
        WHERE Items.user_id = ?
        ORDER BY Items.created_at DESC, Items.id DESC
        LIMIT 8
        """,
        (uid,),
    ).fetchall()

    incoming_claims = db.execute(
        """
        SELECT Claims.*, Items.item_name, Items.status AS item_status, Items.location,
               Users.email AS claimant_email, Users.department AS claimant_department
        FROM Claims
        JOIN Items ON Claims.item_id = Items.id
        JOIN Users ON Claims.claimant_id = Users.id
        WHERE Items.user_id = ?
        ORDER BY CASE Claims.status WHEN 'Pending' THEN 0 WHEN 'Approved' THEN 1 ELSE 2 END,
                 Claims.created_at DESC
        """,
        (uid,),
    ).fetchall()

    my_claims = db.execute(
        """
        SELECT Claims.*, Items.item_name, Items.location, Items.status AS item_status
        FROM Claims
        JOIN Items ON Claims.item_id = Items.id
        WHERE Claims.claimant_id = ?
        ORDER BY Claims.created_at DESC
        LIMIT 6
        """,
        (uid,),
    ).fetchall()

    return render_template(
        "dashboard.html",
        total_reported=total_reported,
        lost_count=lost_count,
        found_count=found_count,
        successful_claims=successful_claims,
        my_items=my_items,
        incoming_claims=incoming_claims,
        my_claims=my_claims,
    )


def handle_report_item(item_type, template_name):
    db = get_db()
    uid = session["user_id"]
    user_row = db.execute("SELECT email, phone FROM Users WHERE id = ?", (uid,)).fetchone()
    default_contact = f"{user_row['email']} · {user_row['phone']}" if user_row else ""
    form_data = {"contact_info": default_contact}

    if request.method == "POST":
        item_name = request.form.get("item_name", "").strip()
        category = request.form.get("category", "").strip()
        description = request.form.get("description", "").strip()
        location = request.form.get("location", "").strip()
        custom_location = request.form.get("custom_location", "").strip()
        if location == "Other" and custom_location:
            location = custom_location
        item_date = request.form.get("item_date", "").strip()
        contact_info = request.form.get("contact_info", "").strip()

        form_data = {
            "item_name": item_name,
            "category": category,
            "description": description,
            "location": location,
            "item_date": item_date,
            "contact_info": contact_info,
        }

        errors = []
        if len(item_name) < 2:
            errors.append("Please enter an item name.")
        if category not in CATEGORIES:
            errors.append("Please choose a valid category.")
        if len(description) < 10:
            errors.append("Please provide a description (at least 10 characters).")
        if len(location) < 2:
            errors.append("Please specify the campus location.")
        if not re.match(r"^\d{4}-\d{2}-\d{2}$", item_date):
            errors.append("Please select a valid date.")
        if len(contact_info) < 5:
            errors.append("Please provide contact information.")

        image_path = ""
        uploaded = request.files.get("image")
        if uploaded and uploaded.filename:
            saved_path, img_err = save_uploaded_image(uploaded)
            if img_err:
                errors.append(img_err)
            else:
                image_path = saved_path

        if errors:
            if image_path:
                remove_uploaded_image(image_path)
            for err in errors:
                flash(err, "error")
            return render_template(template_name, form_data=form_data)

        cur = db.execute(
            """
            INSERT INTO Items (
                user_id, item_name, category, description, location,
                item_date, contact_info, image, item_type, status
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'Active')
            """,
            (uid, item_name, category, description, location, item_date, contact_info, image_path, item_type),
        )
        db.commit()
        new_id = cur.lastrowid

        flash(f"{item_type} item '{item_name}' has been published successfully.", "success")
        return redirect(url_for("item_details", item_id=new_id))

    return render_template(template_name, form_data=form_data)


@app.route("/report-lost", methods=["GET", "POST"])
@login_required
def report_lost():
    return handle_report_item("Lost", "report_lost.html")


@app.route("/report-found", methods=["GET", "POST"])
@login_required
def report_found():
    return handle_report_item("Found", "report_found.html")


@app.route("/browse")
def browse():
    db = get_db()
    q = request.args.get("q", "").strip()
    category = request.args.get("category", "All").strip()
    item_type = request.args.get("type", "All").strip()
    location = request.args.get("location", "All").strip()
    sort = request.args.get("sort", "newest").strip()

    query = """
        SELECT Items.*, Users.full_name AS reporter_name, Users.department AS reporter_department
        FROM Items
        JOIN Users ON Items.user_id = Users.id
        WHERE 1=1
    """
    params = []

    if q:
        like_q = f"%{q}%"
        query += " AND (Items.item_name LIKE ? OR Items.description LIKE ? OR Items.location LIKE ?)"
        params.extend([like_q, like_q, like_q])

    if category and category != "All":
        query += " AND Items.category = ?"
        params.append(category)

    if item_type in ("Lost", "Found"):
        query += " AND Items.item_type = ?"
        params.append(item_type)

    if location and location != "All":
        query += " AND Items.location = ?"
        params.append(location)

    if sort == "oldest":
        query += " ORDER BY Items.created_at ASC, Items.id ASC"
    else:
        sort = "newest"
        query += " ORDER BY Items.created_at DESC, Items.id DESC"

    items = db.execute(query, params).fetchall()

    db_locations = [
        row["location"]
        for row in db.execute("SELECT DISTINCT location FROM Items ORDER BY location ASC").fetchall()
    ]
    all_locations = sorted(set(CAMPUS_LOCATIONS) | set(db_locations))

    return render_template(
        "browse.html",
        items=items,
        all_locations=all_locations,
        filters={
            "q": q,
            "category": category,
            "type": item_type,
            "location": location,
            "sort": sort,
        },
    )


@app.route("/item/<int:item_id>")
def item_details(item_id):
    db = get_db()
    item = db.execute(
        """
        SELECT Items.*, Users.full_name AS reporter_name,
               Users.department AS reporter_department,
               Users.year AS reporter_year
        FROM Items
        JOIN Users ON Items.user_id = Users.id
        WHERE Items.id = ?
        """,
        (item_id,),
    ).fetchone()

    if not item:
        abort(404)

    uid = session.get("user_id")
    is_owner = bool(uid and uid == item["user_id"])

    claims = []
    user_claim = None
    if is_owner:
        claims = db.execute(
            """
            SELECT Claims.*, Users.email AS claimant_email, Users.department AS claimant_department
            FROM Claims
            JOIN Users ON Claims.claimant_id = Users.id
            WHERE Claims.item_id = ?
            ORDER BY CASE Claims.status WHEN 'Pending' THEN 0 WHEN 'Approved' THEN 1 ELSE 2 END,
                     Claims.created_at DESC
            """,
            (item_id,),
        ).fetchall()
    elif uid:
        user_claim = db.execute(
            "SELECT * FROM Claims WHERE item_id = ? AND claimant_id = ? ORDER BY id DESC LIMIT 1",
            (item_id, uid),
        ).fetchone()

    return render_template(
        "item_details.html",
        item=item,
        is_owner=is_owner,
        claims=claims,
        user_claim=user_claim,
    )


@app.route("/item/<int:item_id>/edit", methods=["POST"])
@login_required
def edit_item(item_id):
    db = get_db()
    item = db.execute("SELECT * FROM Items WHERE id = ?", (item_id,)).fetchone()
    if not item:
        abort(404)
    if item["user_id"] != session["user_id"]:
        flash("You are not authorized to modify this item.", "error")
        return redirect(url_for("item_details", item_id=item_id))

    item_name = request.form.get("item_name", "").strip()
    category = request.form.get("category", "").strip()
    description = request.form.get("description", "").strip()
    location = request.form.get("location", "").strip()
    item_date = request.form.get("item_date", "").strip()
    contact_info = request.form.get("contact_info", "").strip()

    if (
        len(item_name) < 2
        or category not in CATEGORIES
        or len(description) < 10
        or len(location) < 2
        or not re.match(r"^\d{4}-\d{2}-\d{2}$", item_date)
        or len(contact_info) < 5
    ):
        flash("Please fill in all fields accurately when updating an item.", "error")
        return redirect(url_for("item_details", item_id=item_id))

    db.execute(
        """
        UPDATE Items
        SET item_name = ?, category = ?, description = ?, location = ?, item_date = ?, contact_info = ?
        WHERE id = ? AND user_id = ?
        """,
        (item_name, category, description, location, item_date, contact_info, item_id, session["user_id"]),
    )
    db.commit()
    flash("Item details updated.", "success")
    return redirect(url_for("item_details", item_id=item_id))


@app.route("/item/<int:item_id>/delete", methods=["POST"])
@login_required
def delete_item(item_id):
    db = get_db()
    item = db.execute("SELECT * FROM Items WHERE id = ?", (item_id,)).fetchone()
    if not item:
        abort(404)
    if item["user_id"] != session["user_id"]:
        flash("You are not authorized to delete this item.", "error")
        return redirect(url_for("item_details", item_id=item_id))

    remove_uploaded_image(item["image"])
    db.execute("DELETE FROM Items WHERE id = ? AND user_id = ?", (item_id, session["user_id"]))
    db.commit()
    flash("Item listing deleted.", "info")
    return redirect(url_for("dashboard"))


@app.route("/item/<int:item_id>/mark-returned", methods=["POST"])
@login_required
def mark_returned(item_id):
    db = get_db()
    item = db.execute("SELECT * FROM Items WHERE id = ?", (item_id,)).fetchone()
    if not item:
        abort(404)
    if item["user_id"] != session["user_id"]:
        flash("Only the original reporter can mark this item as returned.", "error")
        return redirect(url_for("item_details", item_id=item_id))

    db.execute("UPDATE Items SET status = 'Returned' WHERE id = ? AND user_id = ?", (item_id, session["user_id"]))
    db.commit()
    flash("Item marked as returned. Thank you for helping keep campus connected!", "success")
    return redirect(url_for("item_details", item_id=item_id))


@app.route("/claim/<int:item_id>", methods=["GET", "POST"])
@login_required
def claim_item(item_id):
    db = get_db()
    uid = session["user_id"]
    item = db.execute(
        """
        SELECT Items.*, Users.full_name AS reporter_name
        FROM Items
        JOIN Users ON Items.user_id = Users.id
        WHERE Items.id = ?
        """,
        (item_id,),
    ).fetchone()

    if not item:
        abort(404)

    if item["item_type"] != "Found":
        flash("Claim requests can only be submitted for Found items.", "warning")
        return redirect(url_for("item_details", item_id=item_id))

    if item["user_id"] == uid:
        flash("You cannot submit a claim request for an item you reported.", "warning")
        return redirect(url_for("item_details", item_id=item_id))

    if item["status"] == "Returned":
        flash("This item has already been returned to its owner.", "info")
        return redirect(url_for("item_details", item_id=item_id))

    existing_claim = db.execute(
        "SELECT * FROM Claims WHERE item_id = ? AND claimant_id = ? AND status IN ('Pending', 'Approved')",
        (item_id, uid),
    ).fetchone()
    if existing_claim:
        flash("You already have an active claim request for this item.", "info")
        return redirect(url_for("item_details", item_id=item_id))

    user_row = db.execute("SELECT * FROM Users WHERE id = ?", (uid,)).fetchone()
    form_data = {
        "claimant_name": user_row["full_name"],
        "student_id": user_row["student_id"],
        "contact_number": user_row["phone"],
    }

    if request.method == "POST":
        claimant_name = request.form.get("claimant_name", "").strip()
        student_id = request.form.get("student_id", "").strip()
        contact_number = request.form.get("contact_number", "").strip()
        claim_description = request.form.get("claim_description", "").strip()
        identifying_details = request.form.get("identifying_details", "").strip()

        form_data = {
            "claimant_name": claimant_name,
            "student_id": student_id,
            "contact_number": contact_number,
            "claim_description": claim_description,
            "identifying_details": identifying_details,
        }

        errors = []
        if len(claimant_name) < 2:
            errors.append("Please enter your full name.")
        if len(student_id) < 3:
            errors.append("Please enter your Student ID.")
        if len(re.sub(r"\D", "", contact_number)) < 7:
            errors.append("Please enter a valid contact number.")
        if len(claim_description) < 10:
            errors.append("Please describe your ownership (at least 10 characters).")
        if len(identifying_details) < 5:
            errors.append("Please provide additional identifying details to help verify ownership.")

        if errors:
            for err in errors:
                flash(err, "error")
            return render_template("claim.html", item=item, form_data=form_data)

        db.execute(
            """
            INSERT INTO Claims (
                item_id, claimant_id, claimant_name, student_id,
                claim_description, identifying_details, contact_number, status
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, 'Pending')
            """,
            (item_id, uid, claimant_name, student_id, claim_description, identifying_details, contact_number),
        )
        if item["status"] == "Active":
            db.execute("UPDATE Items SET status = 'Pending Claim' WHERE id = ?", (item_id,))
        db.commit()

        flash("Your claim request has been submitted and is pending review by the finder.", "success")
        return redirect(url_for("item_details", item_id=item_id))

    return render_template("claim.html", item=item, form_data=form_data)


@app.route("/claims/<int:claim_id>/action", methods=["POST"])
@login_required
def handle_claim_action(claim_id):
    db = get_db()
    uid = session["user_id"]
    action = request.form.get("action", "").strip()

    claim = db.execute(
        """
        SELECT Claims.*, Items.user_id AS item_owner_id, Items.id AS target_item_id
        FROM Claims
        JOIN Items ON Claims.item_id = Items.id
        WHERE Claims.id = ?
        """,
        (claim_id,),
    ).fetchone()

    if not claim:
        abort(404)

    if claim["item_owner_id"] != uid:
        flash("Only the original item reporter can review claim requests.", "error")
        return redirect(url_for("dashboard"))

    target_item_id = claim["target_item_id"]

    if action == "approve":
        db.execute("UPDATE Claims SET status = 'Approved' WHERE id = ?", (claim_id,))
        db.execute(
            "UPDATE Claims SET status = 'Rejected' WHERE item_id = ? AND id != ? AND status = 'Pending'",
            (target_item_id, claim_id),
        )
        db.execute("UPDATE Items SET status = 'Claim Approved' WHERE id = ?", (target_item_id,))
        db.commit()
        flash("Claim approved! Confirm return once the handoff is complete.", "success")
    elif action == "confirm_return":
        db.execute("UPDATE Claims SET status = 'Approved' WHERE id = ?", (claim_id,))
        db.execute("UPDATE Items SET status = 'Returned' WHERE id = ?", (target_item_id,))
        db.commit()
        flash("Handoff confirmed and item marked as Returned.", "success")
    elif action == "reject":
        db.execute("UPDATE Claims SET status = 'Rejected' WHERE id = ?", (claim_id,))
        remaining = db.execute(
            "SELECT COUNT(*) FROM Claims WHERE item_id = ? AND status IN ('Pending', 'Approved')",
            (target_item_id,),
        ).fetchone()[0]
        if remaining == 0:
            db.execute("UPDATE Items SET status = 'Active' WHERE id = ?", (target_item_id,))
        db.commit()
        flash("Claim request has been rejected.", "info")
    else:
        flash("Unsupported claim action.", "error")

    next_page = request.form.get("next", "")
    if is_safe_redirect_url(next_page):
        return redirect(next_page)
    return redirect(url_for("item_details", item_id=target_item_id))


@app.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    db = get_db()
    uid = session["user_id"]

    if request.method == "POST":
        full_name = request.form.get("full_name", "").strip()
        student_id = request.form.get("student_id", "").strip()
        department = request.form.get("department", "").strip()
        year = request.form.get("year", "").strip()
        phone = request.form.get("phone", "").strip()

        errors = []
        if len(full_name) < 2:
            errors.append("Full name cannot be shorter than 2 characters.")
        if len(student_id) < 3:
            errors.append("Please enter a valid Student / Faculty ID.")
        if not department:
            errors.append("Please select your department.")
        if year not in STUDY_YEARS:
            errors.append("Please select a valid year of study.")
        if len(re.sub(r"\D", "", phone)) < 7:
            errors.append("Please enter a valid phone number.")

        if errors:
            for err in errors:
                flash(err, "error")
        else:
            db.execute(
                """
                UPDATE Users
                SET full_name = ?, student_id = ?, department = ?, year = ?, phone = ?
                WHERE id = ?
                """,
                (full_name, student_id, department, year, phone, uid),
            )
            db.commit()
            session["user_name"] = full_name
            flash("Profile details updated successfully.", "success")
            return redirect(url_for("profile"))

    my_items = db.execute(
        """
        SELECT Items.*,
               (SELECT COUNT(*) FROM Claims WHERE Claims.item_id = Items.id AND Claims.status = 'Pending') AS pending_claims
        FROM Items
        WHERE Items.user_id = ?
        ORDER BY Items.created_at DESC, Items.id DESC
        """,
        (uid,),
    ).fetchall()

    my_claims = db.execute(
        """
        SELECT Claims.*, Items.item_name, Items.location, Items.status AS item_status, Items.item_date
        FROM Claims
        JOIN Items ON Claims.item_id = Items.id
        WHERE Claims.claimant_id = ?
        ORDER BY Claims.created_at DESC, Claims.id DESC
        """,
        (uid,),
    ).fetchall()

    return render_template("profile.html", my_items=my_items, my_claims=my_claims)


@app.route("/about")
def about():
    db = get_db()
    total_returned = db.execute("SELECT COUNT(*) FROM Items WHERE status = 'Returned'").fetchone()[0]
    total_items = db.execute("SELECT COUNT(*) FROM Items").fetchone()[0]
    total_users = db.execute("SELECT COUNT(*) FROM Users").fetchone()[0]
    return render_template(
        "about.html",
        total_returned=total_returned,
        total_items=total_items,
        total_users=total_users,
    )


@app.errorhandler(404)
def page_not_found(e):
    return render_template("404.html"), 404


with app.app_context():
    init_db()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 3000))
    app.run(host="0.0.0.0", port=port, debug=False)
