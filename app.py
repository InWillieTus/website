from flask import Flask, jsonify, request, abort
from flask_cors import CORS
import sqlite3
import os

app = Flask(__name__)
CORS(app)

DB_PATH = os.path.join(os.path.dirname(__file__), "dishes.db")


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
            created_at  DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()


# ── Routes ─────────────────────────────────────────────────────────────────────

@app.route("/api/dishes", methods=["GET"])
def list_dishes():
    category = request.args.get("category")
    conn = get_db()
    if category:
        rows = conn.execute(
            "SELECT * FROM dishes WHERE category = ? ORDER BY created_at DESC",
            (category,)
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
    data = request.get_json(force=True)
    name = data.get("name", "").strip()
    category = data.get("category", "").strip()
    if not name or not category:
        return jsonify({"error": "name and category are required"}), 400

    conn = get_db()
    cur = conn.execute(
        """INSERT INTO dishes (name, category, ingredients, description, prep_time)
           VALUES (?, ?, ?, ?, ?)""",
        (
            name,
            category,
            data.get("ingredients", ""),
            data.get("description", ""),
            data.get("prep_time"),
        ),
    )
    conn.commit()
    new_id = cur.lastrowid
    row = conn.execute("SELECT * FROM dishes WHERE id = ?", (new_id,)).fetchone()
    conn.close()
    return jsonify(dict(row)), 201


@app.route("/api/dishes/<int:dish_id>", methods=["DELETE"])
def delete_dish(dish_id):
    conn = get_db()
    conn.execute("DELETE FROM dishes WHERE id = ?", (dish_id,))
    conn.commit()
    conn.close()
    return jsonify({"deleted": dish_id})


@app.route("/api/categories", methods=["GET"])
def list_categories():
    conn = get_db()
    rows = conn.execute(
        "SELECT DISTINCT category FROM dishes ORDER BY category"
    ).fetchall()
    conn.close()
    return jsonify([r["category"] for r in rows])


if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=5000, debug=False)
