# app/guests/routes.py
from decimal import Decimal, ROUND_HALF_UP
from datetime import datetime
from flask import render_template, request, redirect, url_for, flash, abort
from flask_login import login_required, current_user
from . import guests_bp
from ..utils.decorators import role_required
from ..extensions import db
from ..models import Group, GroupStudent, Student, BannerEvaluation
from sqlalchemy import or_

# ---------------- Dashboard ----------------
@guests_bp.get("/", endpoint="dashboard")
@login_required
@role_required("guest")
def dashboard():
    return render_template("guests/dashboard.html")

# ---------------- Alias legado (/guests/banner) ----------------
@guests_bp.get("/banner", endpoint="banner")
@login_required
@role_required("guest")
def banner_alias():
    # mantém links antigos funcionando
    return redirect(url_for("guests.dashboard"), code=302)

# ---------------- Avaliação do pôster ----------------
@guests_bp.get("/poster")
@login_required
@role_required("guest", "professor")
def poster_eval():
    show_all = request.args.get("all") == "1"
    q = Group.query
    # Se for professor, NÃO mostrar os grupos que ele orienta
    if getattr(current_user, "role_value", "") == "professor":
        q = q.filter(
            or_(
                Group.orientador_user_id.is_(None),
                Group.orientador_user_id != current_user.id,
            )
        )

    # (opcional) continuar ocultando grupos que este usuário já avaliou
    sub = (db.session.query(BannerEvaluation.group_id)
           .filter(BannerEvaluation.evaluator_user_id == current_user.id))
    q = q.filter(~Group.id.in_(sub))

    groups = q.order_by(Group.id.asc()).all()
    return render_template("guests/poster_eval.html", groups=groups)

@guests_bp.get("/poster/modal/<int:group_id>")
@login_required
@role_required("guest", "professor")
def poster_eval_modal(group_id: int):
    g = Group.query.get_or_404(group_id)
    students = (
        Student.query.join(GroupStudent, GroupStudent.student_id == Student.id)
        .filter(GroupStudent.group_id == g.id)
        .order_by(Student.name.asc())
        .all()
    )
    return render_template("guests/_poster_eval_modal.html", group=g, students=students)

# app/guests/routes.py
from decimal import Decimal, ROUND_HALF_UP

@guests_bp.post("/poster/submit")
@login_required
@role_required("guest", "professor")
def poster_submit():
    group_id = request.form.get("group_id", type=int)
    g = db.session.get(Group, group_id)
    if not group_id or not db.session.get(Group, group_id):
        flash("Grupo inválido.", "warning")
        return redirect(url_for("guests.poster_eval"))
    
    # Bloqueia professor de avaliar o próprio grupo
    if getattr(current_user, "role_value", "") == "professor" and g.orientador_user_id == current_user.id:
        flash("Você não pode avaliar o grupo que orienta.", "warning")
        return redirect(url_for("guests.poster_eval"))    

    evaluator_id = getattr(current_user, "id", None) or current_user.get_id()
    try:
        evaluator_id = int(evaluator_id)
    except Exception:
        evaluator_id = None
    if not evaluator_id:
        abort(403)

    # aliases aceitáveis para cada item
    aliases = [
        ("mat", ["mat", "material", "materiais"]),
        ("cri", ["cri", "criatividade"]),
        ("exp", ["exp", "exposicao", "apresentacao"]),
        ("pos", ["pos", "postura"]),
        ("dom", ["dom", "dominio"]),
        ("imp", ["imp", "importancia"]),
        ("tmp", ["tmp", "tempo"]),
    ]

    values = []
    for key, names in aliases:
        raw = None
        for n in names:
            raw = request.form.get(n)
            if raw is not None:
                break
        if raw is None:
            flash("Preencha todos os itens.", "warning")
            return redirect(url_for("guests.poster_eval"))
        try:
            values.append(Decimal(raw))
        except Exception:
            flash("Valor inválido em um dos itens.", "warning")
            return redirect(url_for("guests.poster_eval"))

    avg = (sum(values) / Decimal(len(values))).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    comments = (request.form.get("comments") or "").strip() or None

    existing = (BannerEvaluation.query
                .filter_by(group_id=group_id, evaluator_user_id=evaluator_id)
                .first())
    if existing:
        flash("Você já avaliou este grupo.", "warning")
        return redirect(url_for("guests.poster_eval"))
    else:
        db.session.add(BannerEvaluation(
            group_id=group_id,
            evaluator_user_id=evaluator_id,
            score=avg,
            comments=comments
        ))

    db.session.commit()
    flash("Avaliação registrada com sucesso!", "success")
    return redirect(url_for("guests.poster_eval"))

# ...
from ..models import Group, GroupStudent, Student, BannerEvaluation
# ...

@guests_bp.get("/poster/mine", endpoint="my_evals")
@login_required
@role_required("guest", "professor")
def my_evals():
    # grupos que ESTE convidado já avaliou (sem duplicar)
    rows = (
        db.session.query(Group.id, Group.title)
        .join(BannerEvaluation, BannerEvaluation.group_id == Group.id)
        .filter(BannerEvaluation.evaluator_user_id == current_user.id)
        .group_by(Group.id, Group.title)
        .order_by(Group.id.asc())
        .all()
    )
    items = [{"id": gid, "title": title or "Sem título"} for gid, title in rows]
    return render_template("guests/my_evals.html", items=items)
