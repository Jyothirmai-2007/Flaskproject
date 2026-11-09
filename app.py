from flask import Flask, jsonify, request, send_file
import config
import mysql.connector
import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from io import BytesIO
from datetime import date

app = Flask(__name__)


def fetch_all(query, params=()):
    db = config.connect()
    cursor = db.cursor(dictionary=True)
    try:
        cursor.execute(query, params)
        return cursor.fetchall()
    finally:
        cursor.close()
        db.close()


def fetch_one(query, params=()):
    db = config.connect()
    cursor = db.cursor(dictionary=True)
    try:
        cursor.execute(query, params)
        return cursor.fetchone()
    finally:
        cursor.close()
        db.close()


def execute_query(query, params=()):
    db = config.connect()
    cursor = db.cursor()
    try:
        cursor.execute(query, params)
        db.commit()
        return cursor.lastrowid
    except Exception:
        db.rollback()
        raise
    finally:
        cursor.close()
        db.close()


def valid_positive_id(value):
    try:
        number = int(value)
        return number if number > 0 else None
    except (ValueError, TypeError):
        return None


@app.route("/", methods=["GET"])
def home():
    return jsonify({
        "message": "Library Book Usage Management API",
        "database": "library_book_usage_db",
        "endpoints": [
            "/books",
            "/borrowers",
            "/loans",
            "/reports/available-books",
            "/reports/active-loans",
            "/reports/overdue-loans",
            "/reports/library-summary",
            "/analytics/category-summary",
            "/analytics/borrower-summary",
            "/analytics/availability-numpy",
            "/charts/book-availability",
            "/charts/loan-status"
        ]
    })


@app.route("/books", methods=["GET"])
def get_books():
    return jsonify(fetch_all("SELECT * FROM books ORDER BY book_id"))


@app.route("/books", methods=["POST"])
def add_book():
    data = request.get_json(silent=True)

    required = ["isbn", "title", "author", "category", "copies_available"]

    if not isinstance(data, dict) or any(
        key not in data or data[key] is None
        for key in required
    ):
        return jsonify({
            "error": "Provide isbn, title, author, category and copies_available"
        }), 400

    try:
        copies = int(data["copies_available"])
        if copies < 0:
            return jsonify({
                "error": "copies_available cannot be negative"
            }), 400
    except (ValueError, TypeError):
        return jsonify({
            "error": "copies_available must be a non-negative integer"
        }), 400

    try:
        book_id = execute_query(
            """
            INSERT INTO books
            (isbn, title, author, category, copies_available)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (
                data["isbn"],
                data["title"],
                data["author"],
                data["category"],
                copies
            )
        )
        return jsonify({
            "message": "Book added successfully",
            "book_id": book_id
        }), 201
    except mysql.connector.Error as e:
        return jsonify({"error": str(e)}), 400


@app.route("/books/<int:book_id>", methods=["GET"])
def get_book(book_id):
    book = fetch_one(
        "SELECT * FROM books WHERE book_id = %s",
        (book_id,)
    )
    if not book:
        return jsonify({"error": "Book not found"}), 404
    return jsonify(book)


@app.route("/books/<int:book_id>", methods=["PUT"])
def update_book(book_id):
    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return jsonify({"error": "Provide JSON data"}), 400

    allowed = ["isbn", "title", "author", "category", "copies_available"]
    updates = [(key, data[key]) for key in allowed if key in data]

    if not updates:
        return jsonify({
            "error": "Provide at least one valid field to update"
        }), 400

    if any(value is None for key, value in updates):
        return jsonify({"error": "Values cannot be null"}), 400

    for key, value in updates:
        if key == "copies_available":
            try:
                copies = int(value)
                if copies < 0:
                    return jsonify({
                        "error": "copies_available cannot be negative"
                    }), 400
                updates = [
                    (field, copies if field == key else val)
                    for field, val in updates
                ]
            except (ValueError, TypeError):
                return jsonify({
                    "error": "copies_available must be a non-negative integer"
                }), 400

    book = fetch_one(
        "SELECT * FROM books WHERE book_id = %s",
        (book_id,)
    )
    if not book:
        return jsonify({"error": "Book not found"}), 404

    set_clause = ", ".join(f"{key} = %s" for key, value in updates)
    values = [value for key, value in updates]
    values.append(book_id)

    try:
        execute_query(
            f"UPDATE books SET {set_clause} WHERE book_id = %s",
            tuple(values)
        )
        return jsonify({"message": "Book updated successfully"})
    except mysql.connector.Error as e:
        return jsonify({"error": str(e)}), 400


@app.route("/books/<int:book_id>", methods=["DELETE"])
def delete_book(book_id):
    book = fetch_one(
        "SELECT * FROM books WHERE book_id = %s",
        (book_id,)
    )
    if not book:
        return jsonify({"error": "Book not found"}), 404

    try:
        execute_query(
            "DELETE FROM books WHERE book_id = %s",
            (book_id,)
        )
        return jsonify({"message": "Book deleted successfully"})
    except mysql.connector.Error as e:
        return jsonify({
            "error": "Unable to delete this book. Check whether it has loan records.",
            "details": str(e)
        }), 400


@app.route("/borrowers", methods=["GET"])
def get_borrowers():
    return jsonify(fetch_all(
        "SELECT * FROM borrowers ORDER BY borrower_id"
    ))


@app.route("/borrowers", methods=["POST"])
def add_borrower():
    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return jsonify({"error": "Provide JSON data"}), 400

    if (
        not data.get("borrower_name")
        or data.get("roll_no") is None
        or str(data.get("roll_no")).strip() == ""
    ):
        return jsonify({
            "error": "Provide borrower_name and roll_no"
        }), 400

    try:
        borrower_id = execute_query(
            """
            INSERT INTO borrowers (borrower_name, roll_no)
            VALUES (%s, %s)
            """,
            (data["borrower_name"], data["roll_no"])
        )
        return jsonify({
            "message": "Borrower added successfully",
            "borrower_id": borrower_id
        }), 201
    except mysql.connector.Error as e:
        return jsonify({"error": str(e)}), 400


@app.route("/borrowers/<int:borrower_id>", methods=["GET"])
def get_borrower(borrower_id):
    borrower = fetch_one(
        "SELECT * FROM borrowers WHERE borrower_id = %s",
        (borrower_id,)
    )
    if not borrower:
        return jsonify({"error": "Borrower not found"}), 404
    return jsonify(borrower)


@app.route("/borrowers/<int:borrower_id>", methods=["PUT"])
def update_borrower(borrower_id):
    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return jsonify({"error": "Provide JSON data"}), 400

    allowed = ["borrower_name", "roll_no"]
    updates = [(key, data[key]) for key in allowed if key in data]

    if not updates:
        return jsonify({
            "error": "Provide at least one valid field to update"
        }), 400

    if any(value is None for key, value in updates):
        return jsonify({"error": "Values cannot be null"}), 400

    borrower = fetch_one(
        "SELECT * FROM borrowers WHERE borrower_id = %s",
        (borrower_id,)
    )
    if not borrower:
        return jsonify({"error": "Borrower not found"}), 404

    set_clause = ", ".join(f"{key} = %s" for key, value in updates)
    values = [value for key, value in updates]
    values.append(borrower_id)

    try:
        execute_query(
            f"UPDATE borrowers SET {set_clause} WHERE borrower_id = %s",
            tuple(values)
        )
        return jsonify({"message": "Borrower updated successfully"})
    except mysql.connector.Error as e:
        return jsonify({"error": str(e)}), 400


@app.route("/borrowers/<int:borrower_id>", methods=["DELETE"])
def delete_borrower(borrower_id):
    borrower = fetch_one(
        "SELECT * FROM borrowers WHERE borrower_id = %s",
        (borrower_id,)
    )
    if not borrower:
        return jsonify({"error": "Borrower not found"}), 404

    try:
        execute_query(
            "DELETE FROM borrowers WHERE borrower_id = %s",
            (borrower_id,)
        )
        return jsonify({"message": "Borrower deleted successfully"})
    except mysql.connector.Error as e:
        return jsonify({
            "error": "Unable to delete this borrower. Check whether they have loan records.",
            "details": str(e)
        }), 400


@app.route("/loans", methods=["GET"])
def get_loans():
    query = """
        SELECT l.*, b.title, br.borrower_name, br.roll_no
        FROM loans l
        JOIN books b ON l.book_id = b.book_id
        JOIN borrowers br ON l.borrower_id = br.borrower_id
        ORDER BY l.loan_id
    """
    return jsonify(fetch_all(query))


@app.route("/loans", methods=["POST"])
def add_loan():
    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return jsonify({"error": "Provide JSON data"}), 400

    book_id = valid_positive_id(data.get("book_id"))
    borrower_id = valid_positive_id(data.get("borrower_id"))

    if book_id is None or borrower_id is None:
        return jsonify({
            "error": "book_id and borrower_id must be positive integers"
        }), 400

    issue_date = data.get("issue_date", date.today().isoformat())
    due_date = data.get("due_date")

    if not due_date:
        return jsonify({
            "error": "Provide due_date in YYYY-MM-DD format"
        }), 400

    try:
        issue_date = date.fromisoformat(issue_date)
        due_date = date.fromisoformat(due_date)

        if due_date < issue_date:
            return jsonify({
                "error": "due_date cannot be earlier than issue_date"
            }), 400
    except (ValueError, TypeError):
        return jsonify({
            "error": "Dates must use YYYY-MM-DD format"
        }), 400

    db = config.connect()
    cursor = db.cursor(dictionary=True)

    try:
        cursor.execute(
            """
            SELECT copies_available
            FROM books
            WHERE book_id = %s
            FOR UPDATE
            """,
            (book_id,)
        )
        book = cursor.fetchone()

        if not book:
            db.rollback()
            return jsonify({"error": "Book not found"}), 404

        if book["copies_available"] <= 0:
            db.rollback()
            return jsonify({"error": "No copies available"}), 400

        cursor.execute(
            "SELECT borrower_id FROM borrowers WHERE borrower_id = %s",
            (borrower_id,)
        )
        if not cursor.fetchone():
            db.rollback()
            return jsonify({"error": "Borrower not found"}), 404

        cursor.execute(
            """
            INSERT INTO loans
            (book_id, borrower_id, issue_date, due_date, return_date)
            VALUES (%s, %s, %s, %s, NULL)
            """,
            (
                book_id,
                borrower_id,
                issue_date.isoformat(),
                due_date.isoformat()
            )
        )
        loan_id = cursor.lastrowid

        cursor.execute(
            """
            UPDATE books
            SET copies_available = copies_available - 1
            WHERE book_id = %s
            """,
            (book_id,)
        )

        db.commit()

        return jsonify({
            "message": "Book issued successfully",
            "loan_id": loan_id
        }), 201

    except mysql.connector.Error as e:
        db.rollback()
        return jsonify({"error": str(e)}), 400

    finally:
        cursor.close()
        db.close()


@app.route("/loans/<int:loan_id>", methods=["GET"])
def get_loan(loan_id):
    query = """
        SELECT l.*, b.title, br.borrower_name, br.roll_no
        FROM loans l
        JOIN books b ON l.book_id = b.book_id
        JOIN borrowers br ON l.borrower_id = br.borrower_id
        WHERE l.loan_id = %s
    """
    loan = fetch_one(query, (loan_id,))

    if not loan:
        return jsonify({"error": "Loan not found"}), 404

    return jsonify(loan)


@app.route("/loans/<int:loan_id>", methods=["PUT"])
def update_loan(loan_id):
    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return jsonify({"error": "Provide JSON data"}), 400

    allowed = ["issue_date", "due_date", "return_date"]
    updates = [(key, data[key]) for key in allowed if key in data]

    if not updates:
        return jsonify({
            "error": "Provide issue_date, due_date or return_date"
        }), 400

    for key, value in updates:
        if value is not None:
            try:
                date.fromisoformat(value)
            except (ValueError, TypeError):
                return jsonify({
                    "error": f"{key} must use YYYY-MM-DD format"
                }), 400

    loan = fetch_one(
        "SELECT * FROM loans WHERE loan_id = %s",
        (loan_id,)
    )
    if not loan:
        return jsonify({"error": "Loan not found"}), 404

    if any(key == "return_date" for key, value in updates):
        new_return_date = dict(updates)["return_date"]
        was_returned = loan["return_date"] is not None
        will_be_returned = new_return_date is not None

        if was_returned != will_be_returned:
            return jsonify({
                "error": "Use PUT /loans/<loan_id>/return to return a book. "
                         "Directly changing return_date is not allowed."
            }), 400

    set_clause = ", ".join(f"{key} = %s" for key, value in updates)
    values = [value for key, value in updates]
    values.append(loan_id)

    try:
        execute_query(
            f"UPDATE loans SET {set_clause} WHERE loan_id = %s",
            tuple(values)
        )
        return jsonify({"message": "Loan updated successfully"})
    except mysql.connector.Error as e:
        return jsonify({"error": str(e)}), 400


@app.route("/loans/<int:loan_id>", methods=["DELETE"])
def delete_loan(loan_id):
    db = config.connect()
    cursor = db.cursor(dictionary=True)

    try:
        cursor.execute(
            """
            SELECT book_id, return_date
            FROM loans
            WHERE loan_id = %s
            FOR UPDATE
            """,
            (loan_id,)
        )
        loan = cursor.fetchone()

        if not loan:
            db.rollback()
            return jsonify({"error": "Loan not found"}), 404

        if loan["return_date"] is None:
            cursor.execute(
                """
                UPDATE books
                SET copies_available = copies_available + 1
                WHERE book_id = %s
                """,
                (loan["book_id"],)
            )

        cursor.execute(
            "DELETE FROM loans WHERE loan_id = %s",
            (loan_id,)
        )
        db.commit()

        return jsonify({"message": "Loan deleted successfully"})

    except mysql.connector.Error as e:
        db.rollback()
        return jsonify({"error": str(e)}), 400

    finally:
        cursor.close()
        db.close()


@app.route("/loans/<int:loan_id>/return", methods=["PUT"])
def return_loan(loan_id):
    db = config.connect()
    cursor = db.cursor(dictionary=True)

    try:
        cursor.execute(
            """
            SELECT book_id, return_date
            FROM loans
            WHERE loan_id = %s
            FOR UPDATE
            """,
            (loan_id,)
        )
        loan = cursor.fetchone()

        if not loan:
            db.rollback()
            return jsonify({"error": "Loan not found"}), 404

        if loan["return_date"] is not None:
            db.rollback()
            return jsonify({
                "error": "Book has already been returned"
            }), 400

        return_date = date.today().isoformat()

        cursor.execute(
            "UPDATE loans SET return_date = %s WHERE loan_id = %s",
            (return_date, loan_id)
        )

        cursor.execute(
            """
            UPDATE books
            SET copies_available = copies_available + 1
            WHERE book_id = %s
            """,
            (loan["book_id"],)
        )

        db.commit()
        return jsonify({"message": "Book returned successfully"})

    except mysql.connector.Error as e:
        db.rollback()
        return jsonify({"error": str(e)}), 400

    finally:
        cursor.close()
        db.close()


@app.route("/reports/available-books", methods=["GET"])
def available_books():
    query = """
        SELECT *
        FROM books
        WHERE copies_available > 0
        ORDER BY title
    """
    return jsonify(fetch_all(query))


@app.route("/reports/active-loans", methods=["GET"])
def active_loans():
    query = """
        SELECT l.*, b.title, br.borrower_name, br.roll_no
        FROM loans l
        JOIN books b ON l.book_id = b.book_id
        JOIN borrowers br ON l.borrower_id = br.borrower_id
        WHERE l.return_date IS NULL
        ORDER BY l.due_date
    """
    return jsonify(fetch_all(query))


@app.route("/reports/overdue-loans", methods=["GET"])
def overdue_loans():
    query = """
        SELECT l.*, b.title, br.borrower_name, br.roll_no
        FROM loans l
        JOIN books b ON l.book_id = b.book_id
        JOIN borrowers br ON l.borrower_id = br.borrower_id
        WHERE l.return_date IS NULL AND l.due_date < %s
        ORDER BY l.due_date
    """
    return jsonify(fetch_all(query, (date.today().isoformat(),)))


@app.route("/reports/library-summary", methods=["GET"])
def library_summary():
    query = """
        SELECT
            (SELECT COUNT(*) FROM books) AS total_titles,
            (SELECT COALESCE(SUM(copies_available), 0)
             FROM books) AS available_copies,
            (SELECT COUNT(*) FROM borrowers) AS total_borrowers,
            (SELECT COUNT(*) FROM loans) AS total_loans,
            (SELECT COUNT(*) FROM loans
             WHERE return_date IS NULL) AS active_loans
    """
    return jsonify(fetch_one(query))


@app.route("/analytics/category-summary", methods=["GET"])
def category_summary():
    rows = fetch_all("""
        SELECT category, title, copies_available
        FROM books
    """)

    if not rows:
        return jsonify([])

    df = pd.DataFrame(rows)

    summary = df.groupby("category").agg(
        total_titles=("title", "count"),
        total_available_copies=("copies_available", "sum")
    ).reset_index()

    return jsonify(summary.to_dict(orient="records"))


@app.route("/analytics/borrower-summary", methods=["GET"])
def borrower_summary():
    query = """
        SELECT
            br.borrower_id,
            br.borrower_name,
            br.roll_no,
            COUNT(l.loan_id) AS total_loans
        FROM borrowers br
        LEFT JOIN loans l ON br.borrower_id = l.borrower_id
        GROUP BY br.borrower_id, br.borrower_name, br.roll_no
        ORDER BY total_loans DESC
    """
    return jsonify(fetch_all(query))


@app.route("/analytics/availability-numpy", methods=["GET"])
def availability_numpy():
    rows = fetch_all("SELECT copies_available FROM books")

    values = np.array(
        [row["copies_available"] for row in rows],
        dtype=int
    )

    if values.size == 0:
        return jsonify({
            "total_available_copies": 0,
            "average_available_copies": 0,
            "maximum_available_copies": 0,
            "minimum_available_copies": 0
        })

    return jsonify({
        "total_available_copies": int(np.sum(values)),
        "average_available_copies": float(np.mean(values)),
        "maximum_available_copies": int(np.max(values)),
        "minimum_available_copies": int(np.min(values))
    })


@app.route("/charts/book-availability", methods=["GET"])
def book_availability_chart():
    rows = fetch_all("""
        SELECT title, copies_available
        FROM books
        ORDER BY book_id
    """)

    if not rows:
        return jsonify({"error": "No books available"}), 404

    titles = [row["title"] for row in rows]
    copies = [row["copies_available"] for row in rows]

    plt.figure(figsize=(14, 7))
    plt.bar(titles, copies)
    plt.xlabel("Book Title")
    plt.ylabel("Available Copies")
    plt.title("Book Availability")
    plt.xticks(rotation=90)
    plt.tight_layout()

    image_data = BytesIO()

    try:
        plt.savefig(image_data, format="png")
        image_data.seek(0)
    finally:
        plt.close()

    return send_file(image_data, mimetype="image/png")


@app.route("/charts/loan-status", methods=["GET"])
def loan_status_chart():
    rows = fetch_all("""
        SELECT
            COALESCE(SUM(
                CASE WHEN return_date IS NULL THEN 1 ELSE 0 END
            ), 0) AS active_loans,
            COALESCE(SUM(
                CASE WHEN return_date IS NOT NULL THEN 1 ELSE 0 END
            ), 0) AS returned_loans
        FROM loans
    """)

    active = int(rows[0]["active_loans"])
    returned = int(rows[0]["returned_loans"])

    plt.figure(figsize=(7, 7))

    if active + returned == 0:
        plt.text(
            0.5, 0.5, "No loan data available",
            ha="center", va="center"
        )
        plt.axis("off")
    else:
        plt.pie(
            [active, returned],
            labels=["Active Loans", "Returned Loans"],
            autopct="%1.1f%%"
        )

    plt.title("Loan Status")

    image_data = BytesIO()

    try:
        plt.savefig(image_data, format="png", bbox_inches="tight")
        image_data.seek(0)
    finally:
        plt.close()

    return send_file(image_data, mimetype="image/png")


if __name__ == "__main__":
    app.run(debug=True)