from flask import render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user
from . import auth_bp
from .forms import LoginForm, AccountForm
from ..models import User
from ..extensions import db

@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("index"))
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data.strip().lower()).first()
        if user and user.check_password(form.password.data) and user.is_active:
            login_user(user, remember=form.remember.data)
            
            from flask import session
            session.pop("role", None)  # se existir legado
            
            flash("Bem-vindo(a)!", "success")
            next_page = request.args.get("next") or url_for("index")
            return redirect(next_page)
        flash("Credenciais inválidas.", "danger")
    return render_template("auth/login.html", form=form)

@auth_bp.route("/logout", methods=["POST"])
@login_required
def logout():
    logout_user()
    flash("Sessão encerrada.", "info")
    return redirect(url_for("auth.login"))

@auth_bp.route("/account", methods=["GET", "POST"])
@login_required
def account():
    form = AccountForm(obj=current_user)
    if form.validate_on_submit():
        # Nome
        current_user.full_name = form.full_name.data.strip()

        # E-mail (único)
        new_email = form.email.data.strip().lower()
        if new_email != current_user.email:
            if User.query.filter(User.email == new_email, User.id != current_user.id).first():
                flash("Este e-mail já está em uso.", "warning")
                return render_template("auth/account.html", form=form)
            current_user.email = new_email

        # Troca de senha (opcional)
        cp = (form.current_password.data or "").strip()
        np = (form.new_password.data or "").strip()
        cn = (form.confirm_new_password.data or "").strip()
        if cp or np or cn:
            if not cp or not np:
                flash("Para trocar a senha, informe a senha atual e a nova senha.", "danger")
                return render_template("auth/account.html", form=form)
            if not current_user.check_password(cp):
                flash("Senha atual incorreta.", "danger")
                return render_template("auth/account.html", form=form)
            current_user.set_password(np)

        db.session.commit()
        flash("Conta atualizada com sucesso.", "success")
        return redirect(url_for("auth.account"))

    return render_template("auth/account.html", form=form)
