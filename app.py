from flask import Flask, jsonify, request, abort, send_from_directory
from flask_cors import CORS
import sqlite3
import os
import uuid
from werkzeug.utils import secure_filename

app = Flask(__name__)
CORS(app)

DB_PATH      = os.path.join(os.path.dirname(__file__), "dishes.db")
UPLOAD_DIR   = os.path.join(os.path.dirname(__file__), "static", "uploads")
ALLOWED_EXT  = {"jpg", "jpeg", "png", "webp", "gif"}
MAX_SIZE_MB  = 8

os.makedirs(UPLOAD_DIR, exist_ok=True)


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS dishes (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            name        TEXT NOT NULL,
            category    TEXT NOT NULL,
            ingredients TEXT,
            description TEXT,
            prep_time   INTEGER,
            image_path  TEXT,
            created_at  DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    # Add image_path column if upgrading from previous version
    try:
        conn.execute("ALTER TABLE dishes ADD COLUMN image_path TEXT")
    except Exception:
        pass
    conn.commit()
    conn.close()


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXT


# ── Routes ─────────────────────────────────────────────────────────────────────


@app.route("/")
def serve_index():
    return send_from_directory(os.path.dirname(__file__), "index.html")


@app.route("/<path:filename>")
def serve_static_pages(filename):
    base = os.path.dirname(__file__)
    # Try exact file first, then .html extension
    if os.path.exists(os.path.join(base, filename)):
        return send_from_directory(base, filename)
    return send_from_directory(base, filename + ".html")


@app.route("/api/dishes", methods=["GET"])
def list_dishes():
    category = request.args.get("category")
    conn = get_db()
    if category:
        rows = conn.execute(
            "SELECT * FROM dishes WHERE category = ? ORDER BY created_at DESC", (category,)
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM dishes ORDER BY created_at DESC"
        ).fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])


@app.route("/api/dishes/<int:dish_id>", methods=["GET"])
def get_dish(dish_id):
    conn = get_db()
    row = conn.execute("SELECT * FROM dishes WHERE id = ?", (dish_id,)).fetchone()
    conn.close()
    if row is None:
        abort(404)
    return jsonify(dict(row))


@app.route("/api/dishes", methods=["POST"])
def create_dish():
    # Accepts multipart/form-data (with optional image) OR JSON (no image)
    if request.content_type and "multipart/form-data" in request.content_type:
        name     = request.form.get("name", "").strip()
        category = request.form.get("category", "").strip()
        if not name or not category:
            return jsonify({"error": "name and category are required"}), 400

        image_path = None
        file = request.files.get("image")
        if file and file.filename:
            if not allowed_file(file.filename):
                return jsonify({"error": "Image must be jpg, png, webp or gif"}), 400
            ext      = file.filename.rsplit(".", 1)[1].lower()
            filename = f"{uuid.uuid4().hex}.{ext}"
            file.save(os.path.join(UPLOAD_DIR, filename))
            image_path = f"/static/uploads/{filename}"

        conn = get_db()
        cur = conn.execute(
            """INSERT INTO dishes (name, category, ingredients, description, prep_time, image_path)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (
                name,
                category,
                request.form.get("ingredients", ""),
                request.form.get("description", ""),
                request.form.get("prep_time") or None,
                image_path,
            ),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM dishes WHERE id = ?", (cur.lastrowid,)).fetchone()
        conn.close()
        return jsonify(dict(row)), 201

    else:
        # JSON fallback (no image)
        data     = request.get_json(force=True)
        name     = data.get("name", "").strip()
        category = data.get("category", "").strip()
        if not name or not category:
            return jsonify({"error": "name and category are required"}), 400
        conn = get_db()
        cur = conn.execute(
            """INSERT INTO dishes (name, category, ingredients, description, prep_time)
               VALUES (?, ?, ?, ?, ?)""",
            (name, category, data.get("ingredients", ""), data.get("description", ""), data.get("prep_time")),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM dishes WHERE id = ?", (cur.lastrowid,)).fetchone()
        conn.close()
        return jsonify(dict(row)), 201


@app.route("/api/dishes/<int:dish_id>", methods=["PUT"])
def update_dish(dish_id):
    conn = get_db()
    existing = conn.execute("SELECT * FROM dishes WHERE id = ?", (dish_id,)).fetchone()
    if existing is None:
        conn.close()
        abort(404)

    image_path = existing["image_path"]  # keep existing image by default

    if request.content_type and "multipart/form-data" in request.content_type:
        name     = request.form.get("name", "").strip()
        category = request.form.get("category", "").strip()
        if not name or not category:
            conn.close()
            return jsonify({"error": "name and category are required"}), 400

        file = request.files.get("image")
        if file and file.filename:
            if not allowed_file(file.filename):
                conn.close()
                return jsonify({"error": "Image must be jpg, png, webp or gif"}), 400
            # Remove old image if it exists
            if image_path:
                old_file = os.path.join(UPLOAD_DIR, image_path.split("/")[-1])
                if os.path.exists(old_file):
                    os.remove(old_file)
            ext      = file.filename.rsplit(".", 1)[1].lower()
            filename = f"{uuid.uuid4().hex}.{ext}"
            file.save(os.path.join(UPLOAD_DIR, filename))
            image_path = f"/static/uploads/{filename}"

        # Allow explicit removal of image
        if request.form.get("remove_image") == "1" and image_path:
            old_file = os.path.join(UPLOAD_DIR, image_path.split("/")[-1])
            if os.path.exists(old_file):
                os.remove(old_file)
            image_path = None

        conn.execute(
            """UPDATE dishes SET name=?, category=?, ingredients=?, description=?, prep_time=?, image_path=?
               WHERE id=?""",
            (
                name,
                category,
                request.form.get("ingredients", ""),
                request.form.get("description", ""),
                request.form.get("prep_time") or None,
                image_path,
                dish_id,
            ),
        )
    else:
        data     = request.get_json(force=True)
        name     = data.get("name", "").strip()
        category = data.get("category", "").strip()
        if not name or not category:
            conn.close()
            return jsonify({"error": "name and category are required"}), 400
        conn.execute(
            """UPDATE dishes SET name=?, category=?, ingredients=?, description=?, prep_time=?
               WHERE id=?""",
            (name, category, data.get("ingredients", ""), data.get("description", ""),
             data.get("prep_time"), dish_id),
        )

    conn.commit()
    row = conn.execute("SELECT * FROM dishes WHERE id = ?", (dish_id,)).fetchone()
    conn.close()
    return jsonify(dict(row))


@app.route("/api/dishes/<int:dish_id>", methods=["DELETE"])
def delete_dish(dish_id):
    conn = get_db()
    row = conn.execute("SELECT image_path FROM dishes WHERE id = ?", (dish_id,)).fetchone()
    if row and row["image_path"]:
        filename = row["image_path"].split("/")[-1]
        filepath = os.path.join(UPLOAD_DIR, filename)
        if os.path.exists(filepath):
            os.remove(filepath)
    conn.execute("DELETE FROM dishes WHERE id = ?", (dish_id,))
    conn.commit()
    conn.close()
    return jsonify({"deleted": dish_id})


@app.route("/api/categories", methods=["GET"])
def list_categories():
    conn = get_db()
    rows = conn.execute("SELECT DISTINCT category FROM dishes ORDER BY category").fetchall()
    conn.close()
    return jsonify([r["category"] for r in rows])


if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=5000, debug=True)
