from flask import Blueprint, request, render_template, redirect, url_for, session
from ..services.auth_service import AuthService

admin_bp = Blueprint("admin", __name__)
ADMIN_PASSWORD = "dober@03"

@admin_bp.route("/", methods=["GET"])
def index():
    if not session.get("admin_authenticated"):
        return render_template("admin.html", authenticated=False)
    
    tokens = AuthService.get_valid_keys()
    return render_template("admin.html", authenticated=True, tokens=tokens)

@admin_bp.route("/login", methods=["POST"])
def login():
    password = request.form.get("password")
    if password == ADMIN_PASSWORD:
        session["admin_authenticated"] = True
        return redirect(url_for("admin.index"))
    return render_template("admin.html", authenticated=False, error="Invalid Password")

@admin_bp.route("/add_token", methods=["POST"])
def add_token():
    if not session.get("admin_authenticated"):
        return redirect(url_for("admin.index"))
    
    token = request.form.get("token")
    if token:
        tokens = AuthService.get_valid_keys()
        if token not in tokens:
            tokens.append(token)
            AuthService.update_valid_keys(tokens)
    return redirect(url_for("admin.index"))

@admin_bp.route("/delete_token", methods=["POST"])
def delete_token():
    if not session.get("admin_authenticated"):
        return redirect(url_for("admin.index"))
    
    token = request.form.get("token")
    if token:
        tokens = AuthService.get_valid_keys()
        if token in tokens:
            tokens.remove(token)
            AuthService.update_valid_keys(tokens)
    return redirect(url_for("admin.index"))
