from flask  import Flask, session, render_template, redirect, request, flash
from cs50 import SQL
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from flask import send_from_directory
import os


app = Flask(__name__, template_folder="templates", static_folder="static")
app.secret_key = "roronoa_zoro"
db =  SQL("sqlite:///users.db")

UPLOAD_FOLDER = "uploads"
PROFILE_PIC_FOLDER = "static/profile_pics"

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

PROFILE_UPLOAD_FOLDER = os.path.join(app.static_folder, "profile_pics")
os.makedirs(PROFILE_UPLOAD_FOLDER, exist_ok=True)



@app.route("/")
def home():
    if "user_id" in session:
        return redirect("/dashboard")
    return render_template("home.html")

@app.route("/register",methods=["GET","POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username")
        email = request.form.get("email")
        password = request.form.get("password")
        confirmation = request.form.get("confirmation")
        if not email:
            flash("Please enter your email.", "error")
            return redirect("/register")

        if not username:
            flash("Please enter your username.", "error")
            return redirect("/register")

        if not password:
            flash("Please enter your password.", "error")
            return redirect("/register")

        if password != confirmation:
            flash("Passwords do not match.", "error")
            return redirect("/register")

        match = db.execute("SELECT * FROM users WHERE username = ? OR email = ?", username, email)
        if len(match) > 0:
            flash("Username or email already exists.", "error")
            return redirect("/register")

        hash_pass = generate_password_hash(password)
        db.execute("INSERT INTO users (username, email, password_hash) VALUES (?, ?, ?)",username, email, hash_pass)

        new_user = db.execute("SELECT * FROM users WHERE username = ?", username)
        session["user_id"] = new_user[0]["id"]
        flash("Account created successfully.", "success")

        return redirect("/dashboard")
    return render_template("register.html")

@app.route("/login",methods=["GET","POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        if not username:
            flash("Please enter your username.", "error")
            return redirect("/login")
        if not password:
            flash("Please enter your password.", "error")
            return redirect("/login")

        match = db.execute("SELECT * FROM users WHERE username = ?",username)
        if  len(match) != 1:
           flash("user not found.", "error")
           return redirect("/register")
        if  not check_password_hash(match[0]["password_hash"],password):
            flash("password is wrong", "error")
            return redirect("/login")
        session["user_id"] = match[0]["id"]
        return redirect("/dashboard")
    return render_template("login.html")

@app.route("/dashboard")
def dashboard():
    if "user_id" not in session:
        flash("Please login.","error")
        return redirect("/login")

    user = db.execute("SELECT * FROM users WHERE id = ?", session["user_id"])
    pinned_pdfs = db.execute(
        "SELECT * FROM pdfs WHERE user_id = ? AND is_pinned = 1 ORDER BY uploaded_at DESC",
        session["user_id"]
    )
    uploaded_pdfs = db.execute(
        "SELECT * FROM pdfs WHERE user_id = ? ORDER BY uploaded_at DESC",
        session["user_id"]
    )

    return render_template(
        "dashboard.html",
        user=user[0],
        pinned_pdfs=pinned_pdfs,
        uploaded_pdfs=uploaded_pdfs
    )

@app.route("/upload_pdf", methods=["POST"])
def upload():
    if "user_id" not in session:
        flash("Please login.","error")
        return redirect("/login")

    title = request.form.get("title")
    pdf = request.files.get("pdf_file")

    if not title:
        flash("Enter PDF title.", "error")
        return redirect("/dashboard")
    if not pdf or pdf.filename == "":
        flash("Choose a PDF file.", "error")
        return redirect("/dashboard")

    filename = secure_filename(pdf.filename)
    pdf.save(os.path.join(UPLOAD_FOLDER, filename))

    db.execute(
        "INSERT INTO pdfs (user_id, title, filename) VALUES (?, ?, ?)",
        session["user_id"], title, filename
    )

    return redirect("/dashboard")

@app.route("/pin/<int:pdf_id>")
def pin(pdf_id):
    if "user_id" not in session:
        flash("Please login.","error")
        return redirect("/login")
    db.execute("UPDATE pdfs SET is_pinned = 1 WHERE id = ? AND user_id =?",pdf_id, session["user_id"])
    return redirect("/dashboard")
@app.route("/unpin/<int:pdf_id>")
def unpin(pdf_id):
    if "user_id" not in session:
        flash("Please login.","error")
        return redirect("/login")
    db.execute("UPDATE pdfs SET is_pinned = 0 WHERE id = ? AND user_id =?",pdf_id, session["user_id"])
    return redirect("/dashboard")

@app.route("/upload_profile_pic", methods=["POST"])
def upload_profile_pic():
    if "user_id" not in session:
        flash("Please login.","error")
        return redirect("/login")

    file = request.files.get("profile_pic")

    if not file or file.filename == "":
        flash("Pick a profile picture.","error")
        return redirect("/dashboard")

    filename = secure_filename(file.filename)
    filepath = os.path.join(PROFILE_UPLOAD_FOLDER, filename)
    file.save(filepath)

    db.execute(
        "UPDATE users SET profile_pic = ? WHERE id = ?",
        filename, session["user_id"]
    )

    return redirect("/dashboard")


@app.route("/open_pdf/<int:pdf_id>")
def open_pdf(pdf_id):
    if "user_id" not in session:
        flash("Please login.","error")
        return redirect("/login")

    pdf = db.execute("SELECT * FROM pdfs WHERE id = ?", pdf_id)

    if not pdf:
        flash("PDF not exist.","error")
        return redirect("/dashboard")
    pdf = pdf[0]

    if pdf["user_id"] == session["user_id"]:
        file_path = os.path.join(UPLOAD_FOLDER, pdf["filename"])
        if not os.path.exists(file_path):
            return "File not found in uploads folder"
        return send_from_directory(UPLOAD_FOLDER, pdf["filename"])

    shared = db.execute(
        "SELECT * FROM shared_users WHERE owner_id = ? AND shared_with = ?",
        pdf["user_id"], session["user_id"]
    )

    if shared:
        file_path = os.path.join(UPLOAD_FOLDER, pdf["filename"])
        if not os.path.exists(file_path):
            return "File not found in uploads folder"
        return send_from_directory(UPLOAD_FOLDER, pdf["filename"])

    return "Access denied"

@app.route("/delete_pdf/<int:pdf_id>", methods=["POST"])
def delete_pdf(pdf_id):
    if "user_id" not in session:
        flash("Please login.", "error")
        return redirect("/login")

    pdf = db.execute(
        "SELECT * FROM pdfs WHERE id = ? AND user_id = ?",
        pdf_id, session["user_id"]
    )

    if not pdf:
        flash("PDF not found or access denied.", "error")
        return redirect("/dashboard")

    pdf = pdf[0]
    file_path = os.path.join(UPLOAD_FOLDER, pdf["filename"])

    db.execute(
        "DELETE FROM pdfs WHERE id = ? AND user_id = ?",
        pdf_id, session["user_id"]
    )

    if os.path.exists(file_path):
        os.remove(file_path)

    flash("PDF deleted successfully.", "success")
    return redirect("/dashboard")

@app.route("/shared")
def shared():
    if "user_id" not in session:
        flash("Please login.","error")
        return redirect("/login")
    users=db.execute("SELECT users.id, users.username FROM  shared_users JOIN users ON shared_users.owner_id = users.id WHERE shared_users.shared_with = ? ",session["user_id"])

    return render_template("shared.html", users=users)

@app.route("/shared/<int:user_id>")
def view_shared_user(user_id):
    if "user_id" not in session:
        flash("Please login.","error")
        return redirect("/login")
    access = db.execute(
        "SELECT * FROM shared_users WHERE owner_id = ? AND shared_with = ?",
        user_id, session["user_id"]
    )

    if not access:
        flash("Access denied")
        return redirect("/shared")

    pdfs=db.execute("SELECT * FROM pdfs WHERE user_id =? ORDER BY uploaded_at DESC",user_id)
    user = db.execute("SELECT username FROM users WHERE id =?",user_id)
    if not user:
        return "User not exist"
    return render_template("shared_user.html", pdfs=pdfs, user=user[0])


@app.route("/share_account",methods=["GET","POST"])
def share():
    if "user_id" not in session:
        flash("Please login.","error")
        return redirect("/login")
    if request.method == "GET":
        return redirect("/dashboard")

    username = request.form.get("username")
    if not username:
        flash("Enter username","error")
        return redirect("/dashboard")

    user = db.execute("SELECT id FROM users WHERE username = ?",username)
    if len(user) == 0:
        flash("User not found!","error")
        return redirect("/dashboard")

    if user[0]["id"] == session["user_id"]:
        flash("You cannot share with yourself.","error")
        return redirect("/dashboard")

    existing = db.execute(
        "SELECT * FROM shared_users WHERE owner_id = ? AND shared_with = ?",
        session["user_id"], user[0]["id"]
    )

    if existing:
        flash("Already exists","error")
        return redirect("/dashboard")

    db.execute("INSERT INTO shared_users (owner_id, shared_with) VALUES (?, ?)",session["user_id"], user[0]["id"] )
    flash("Shared successfully!", "success")
    return redirect("/dashboard")





@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)




