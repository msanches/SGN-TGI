from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from sqlalchemy.exc import IntegrityError 
from flask_login import login_required, current_user
from ..utils.decorators import role_required
from . import admin_bp
from ..services.excel_export import export_demo
from ..extensions import db
from ..models import (
    Student, Campus, Offering,
    Group, GroupStudent, GroupProfessor,
    GroupAssessment, BannerEvaluation, Instrument, User, Role
)
from .forms import StudentForm, GroupCreateForm, GroupEditForm, GradeForm
from sqlalchemy import or_
from ..models import User, Role
from .forms import UserForm
from sqlalchemy import func
from ..extensions import bcrypt

# from .forms import AdminGroupGradesForm
from app.services.grades import upsert_assessment, get_assessment_score
from decimal import Decimal
from app.utils.instruments import resolve_instrument

def campus_choices():
    return [(c.id, c.name) for c in Campus.query.order_by(Campus.name.asc()).all()]

def professor_choices(include_placeholder=True):
    # Suporta tanto Enum quanto string na coluna 'role'
    q = (User.query
         .filter(or_(User.role == Role.professor, User.role == "professor"))
         .filter(User.is_active.is_(True))
         .order_by(User.full_name.asc()))
    rows = q.all()
    choices = [(-1, "— Sem orientador —")] if include_placeholder else []
    choices += [(u.id, u.full_name or u.email) for u in rows]
    return choices

# ---- Dashboard / Export ----
@admin_bp.route("/")
@login_required
@role_required("admin")
def dashboard():
    return render_template("admin/dashboard.html")

@admin_bp.route("/export/excel")
@login_required
@role_required("admin")
def export_excel():
    return export_demo()

# ---- Students ----
@admin_bp.route("/students")
@login_required
@role_required("admin")
def students_list():
    q = request.args.get("q", "").strip()
    query = Student.query
    if q:
        like = f"%{q}%"
        query = query.filter((Student.name.ilike(like)) | (Student.rgm.ilike(like)))
    students = query.order_by(Student.name.asc()).all()
    return render_template("admin/students_list.html", students=students, q=q)

@admin_bp.route("/students/new", methods=["GET", "POST"])
@login_required
@role_required("admin")
def students_new():
    form = StudentForm()
    form.campus_id.choices = campus_choices()

    if form.validate_on_submit():
        # Campus por id
        campus = Campus.query.get(form.campus_id.data)
        if campus is None:
            flash("Campus inválido.", "danger")
            return render_template("admin/students_new.html", form=form)

        # Offering por código (cria se não existir)
        code = (form.offering.data or "").strip()
        offering = Offering.query.filter_by(code=code).first()
        if not offering:
            offering = Offering(code=code, description=None)
            db.session.add(offering)
            db.session.flush()

        # RGM único
        if Student.query.filter_by(rgm=form.rgm.data.strip()).first():
            flash("Já existe um aluno com esse RGM.", "warning")
            return render_template("admin/students_new.html", form=form)

        st = Student(
            name=form.name.data.strip(),
            rgm=form.rgm.data.strip(),
            campus_id=campus.id,
            offering_id=offering.id,
        )
        db.session.add(st)
        db.session.commit()
        flash("Aluno cadastrado com sucesso.", "success")
        return redirect(url_for("admin.students_list"))

    return render_template("admin/students_new.html", form=form)

@admin_bp.route("/students/<int:student_id>/edit", methods=["GET", "POST"])
@login_required
@role_required("admin")
def students_edit(student_id):
    s = Student.query.get_or_404(student_id)
    form = StudentForm(obj=s)
    form.campus_id.choices = campus_choices()

    # Pré-seleção do campus no GET
    if request.method == "GET":
        form.campus_id.data = s.campus_id
        form.offering.data = s.offering.code if s.offering else ""

    if form.validate_on_submit():
        s.name = form.name.data.strip()
        s.rgm = form.rgm.data.strip()

        campus = Campus.query.get(form.campus_id.data)
        if campus is None:
            flash("Campus inválido.", "danger")
            return render_template("admin/students_edit.html", form=form, student=s)

        s.campus_id = campus.id

        code = (form.offering.data or "").strip()
        offering = Offering.query.filter_by(code=code).first()
        if not offering:
            offering = Offering(code=code, description=None)
            db.session.add(offering)
            db.session.flush()

        s.offering_id = offering.id

        db.session.commit()
        flash("Aluno atualizado com sucesso.", "success")
        return redirect(url_for("admin.students_list"))

    return render_template("admin/students_edit.html", form=form, student=s)

@admin_bp.route("/students/<int:student_id>/delete", methods=["POST"])
@login_required
@role_required("admin")
def students_delete(student_id):
    st = Student.query.get_or_404(student_id)
    GroupStudent.query.filter_by(student_id=st.id).delete()
    db.session.delete(st); db.session.commit()
    flash("Aluno excluído.", "success")
    return redirect(url_for("admin.students_list"))

# ---- Groups ----
@admin_bp.route("/groups")
@login_required
@role_required("admin")
def groups_list():
    groups = Group.query.order_by(Group.id.asc()).all()
    data = []
    for g in groups:
        members = [gs.student for gs in g.members]  # g.members é query; iterar executa
        orientador = g.orientador.full_name if g.orientador else "—"
        data.append({"g": g, "members": members, "orientador": orientador})
    return render_template("admin/groups_list.html", groups=data)

@admin_bp.route("/groups/new", methods=["GET", "POST"])
@login_required
@role_required("admin")
def groups_new():
    form = GroupCreateForm()

    # Popular o select SEMPRE, antes de validar:
    form.orientador_user_id.choices = professor_choices()

    if request.method == "GET":
        form.orientador_user_id.data = -1  # sentinel "Sem orientador"

    if form.validate_on_submit():
        lines = [ln.strip() for ln in (form.rgms.data or "").splitlines() if ln.strip()]
        students = Student.query.filter(Student.rgm.in_(lines)).all()
        found_rgms = {s.rgm for s in students}
        missing = [r for r in lines if r not in found_rgms]
        if missing:
            flash(f"RGM(s) não encontrados: {', '.join(missing)}", "danger")
            return render_template("admin/groups_new.html", form=form)

        grp = Group(
            title=(form.title.data or "").strip() or None,
        )
        # traduz -1 -> None
        sel = form.orientador_user_id.data
        grp.orientador_user_id = None if sel == -1 else sel

        db.session.add(grp)
        db.session.flush()

        for st in students:
            db.session.add(GroupStudent(group_id=grp.id, student_id=st.id))

        db.session.commit()
        flash(f"Grupo #{grp.id} criado com {len(students)} aluno(s).", "success")
        return redirect(url_for("admin.groups_list"))

    return render_template("admin/groups_new.html", form=form)

@admin_bp.route("/api/students/by_rgm")
@login_required
@role_required("admin")
def api_student_by_rgm():
    rgm = (request.args.get("rgm") or "").strip()
    if not rgm:
        return jsonify({"ok": False, "error": "RGM vazio"}), 400

    s = Student.query.filter_by(rgm=rgm).first()
    if not s:
        return jsonify({"ok": True, "found": False})

    gs = GroupStudent.query.filter_by(student_id=s.id).first()
    in_group = gs is not None
    group_id = gs.group_id if gs else None

    return jsonify({
        "ok": True,
        "found": True,
        "student": {
            "id": s.id,
            "rgm": s.rgm,
            "name": s.name,
            "campus": s.campus.name,
            "offering": s.offering.code,
            "in_group": in_group,
            "group_id": group_id
        }
    })

@admin_bp.route("/groups/<int:group_id>/edit", methods=["GET", "POST"])
@login_required
@role_required("admin")
def groups_edit(group_id):
    group = Group.query.get_or_404(group_id)
    form = GroupEditForm()

    # Popular SEMPRE antes da validação
    form.orientador_user_id.choices = professor_choices()

    if request.method == "GET":
        form.title.data = group.title or ""
        form.orientador_user_id.data = group.orientador_user_id if group.orientador_user_id is not None else -1
        current_rgms = [gs.student.rgm for gs in group.members]  # ajuste conforme seu relacionamento
        form.rgms.data = "\n".join(current_rgms)

    if form.validate_on_submit():
        group.title = (form.title.data or "").strip() or None
        sel = form.orientador_user_id.data
        group.orientador_user_id = None if sel == -1 else sel

        # Atualiza membros a partir do textarea
        lines = [ln.strip() for ln in (form.rgms.data or "").splitlines() if ln.strip()]
        wanted = set(lines)

        # mapa RGM -> Student
        students = Student.query.filter(Student.rgm.in_(wanted)).all()
        found = {s.rgm: s for s in students}
        missing = [r for r in wanted if r not in found]
        if missing:
            flash(f"RGM(s) não encontrados: {', '.join(missing)}", "warning")

        # estado atual
        current_ids = {gs.student_id for gs in group.members}
        wanted_ids  = {found[r].id for r in found}

        # remover quem não está mais
        for gs in list(group.members):
            if gs.student_id not in wanted_ids:
                db.session.delete(gs)

        # adicionar novos
        for sid in wanted_ids - current_ids:
            db.session.add(GroupStudent(group_id=group.id, student_id=sid))

        db.session.commit()
        flash("Grupo atualizado com sucesso.", "success")
        return redirect(url_for("admin.groups_list"))

    members = [gs.student for gs in group.members]
    current_rgms = [s.rgm for s in members]
    return render_template("admin/groups_edit.html", form=form, group=group, members=members, current_rgms=current_rgms)

@admin_bp.route("/groups/<int:group_id>/delete", methods=["POST"])
@login_required
@role_required("admin")
def groups_delete(group_id):
    grp = Group.query.get_or_404(group_id)
    GroupStudent.query.filter_by(group_id=grp.id).delete()
    GroupProfessor.query.filter_by(group_id=grp.id).delete()
    GroupAssessment.query.filter_by(group_id=grp.id).delete()
    BannerEvaluation.query.filter_by(group_id=grp.id).delete()
    db.session.delete(grp); db.session.commit()
    flash("Grupo excluído.", "success")
    return redirect(url_for("admin.groups_list"))

# ---- Notas do Grupo (R1/R2/Paper) ----
@admin_bp.route("/groups/<int:group_id>/grades", methods=["GET", "POST"])
@login_required
@role_required("admin")
def groups_grades(group_id):
    group = Group.query.get_or_404(group_id)
    form = GradeForm()

    if form.validate_on_submit():
        # checkbox -> 0.5 quando marcado senão 0.0
        score_ri  = Decimal("0.5") if form.relatorio_i.data  else Decimal("0.0")
        score_rii = Decimal("0.5") if form.relatorio_ii.data else Decimal("0.0")

        # paper (0..4); se vier vazio, trata como 0.0 (ou mude para None se preferir não criar registro)
        paper_val = form.paper.data
        score_paper = Decimal(str(paper_val)) if paper_val is not None else Decimal("0.0")

        upsert_assessment(group.id, I_RI,    score_ri,    current_user.id)
        upsert_assessment(group.id, I_RII,   score_rii,   current_user.id)
        upsert_assessment(group.id, I_PAPER, score_paper, current_user.id)

        db.session.commit()
        flash("Notas salvas com sucesso.", "success")
        return redirect(url_for("admin.groups_grades", group_id=group.id))

    # Pré-preenche o form
    I_RI    = resolve_instrument("ri")
    I_RII   = resolve_instrument("rii")
    I_PAPER = resolve_instrument("paper")

    ri_score    = get_assessment_score(group.id, I_RI)    or Decimal("0")
    rii_score   = get_assessment_score(group.id, I_RII)   or Decimal("0")
    paper_score = get_assessment_score(group.id, I_PAPER)

    upsert_assessment
    form.relatorio_i.data  = (ri_score  >= Decimal("0.5"))
    form.relatorio_ii.data = (rii_score >= Decimal("0.5"))
    form.paper.data = float(paper_score) if paper_score is not None else None

    members = [gs.student for gs in group.members]
    return render_template("admin/groups_grades.html", group=group, members=members, form=form)

# ---- Users ----
# app/admin/routes.py (mesma função da lista)
@admin_bp.route("/users")
@login_required
def users_list():
    q = (request.args.get("q") or "").strip()
    role_param = (request.args.get("role") or "").strip().lower()

    query = User.query

    if q:
        like = f"%{q}%"
        query = query.filter(or_(User.full_name.ilike(like), User.email.ilike(like)))

    # Funciona se User.role for Enum(Role) OU se existir coluna/prop role_value
    if role_param in {"admin", "professor", "guest"}:
        try:
            # tenta comparar com Enum(Role)
            query = query.filter(User.role == Role(role_param))
        except Exception:
            # fallback para string
            query = query.filter(getattr(User, "role_value") == role_param)

    query = query.order_by(User.full_name.asc())
    users = query.all()

    # Mapa de contagem de grupos por orientador
    counts = (
        db.session.query(Group.orientador_user_id, func.count(Group.id))
        .group_by(Group.orientador_user_id)
        .all()
    )
    group_counts = {uid: cnt for uid, cnt in counts}

    return render_template(
        "admin/users_list.html",
        users=users,
        q=q,
        role=role_param,
        group_counts=group_counts,
    )

@admin_bp.route("/users/new", methods=["GET", "POST"])
@login_required
@role_required("admin")
def users_new():
    form = UserForm()
    if form.validate_on_submit():
        if User.query.filter_by(email=form.email.data.strip().lower()).first():
            flash("Já existe um usuário com este e-mail.", "warning")
            return render_template("admin/user_form.html", form=form, is_new=True)

        user = User(
            full_name=form.full_name.data.strip(),
            email=form.email.data.strip().lower(),
            role=Role(form.role.data),
            is_active=form.is_active.data,
        )
        if form.password.data:
            user.password_hash = bcrypt.generate_password_hash(form.password.data).decode()

        db.session.add(user)
        db.session.commit()
        flash("Usuário criado com sucesso.", "success")
        return redirect(url_for("admin.users_list"))
    return render_template("admin/user_form.html", form=form, is_new=True)

@admin_bp.route("/users/<int:user_id>/edit", methods=["GET", "POST"])
@login_required
@role_required("admin")
def users_edit(user_id):
    user = User.query.get_or_404(user_id)
    form = UserForm(obj=user)

    if form.validate_on_submit():
        user.full_name = form.full_name.data.strip()
        user.email = form.email.data.strip().lower()
        user.is_active = bool(form.is_active.data)

        # normaliza role vindo do form (sempre string: 'admin' | 'professor' | 'guest')
        raw_role = form.role.data
        try:
            # Se seu modelo ainda usa Enum(Role) no banco:
            from ..models import Role as RoleEnum  # se existir
            # Se atualmente user.role é Enum, gravamos Enum; se já é string, gravamos string
            if hasattr(user.role, "value"):   # era Enum na leitura
                user.role = RoleEnum(raw_role)
            else:                             # é string no modelo
                user.role = raw_role
        except Exception:
            # Sem Enum disponível ou coluna é string
            user.role = raw_role

        if form.password.data:
            user.set_password(form.password.data)

        db.session.commit()
        flash("Usuário atualizado com sucesso.", "success")
        return redirect(url_for("admin.users_list"))

    # Pré-preenche no GET sem assumir Enum
    if request.method == "GET":
        form.role.data = (
            getattr(user, "role_value", None)
            or (user.role.value if hasattr(user.role, "value") else user.role)
        )

    return render_template("admin/user_form.html", form=form, is_new=False)

@admin_bp.route("/users/<int:user_id>/delete", methods=["POST"])
@login_required
@role_required("admin")
def users_delete(user_id):
    user = User.query.get_or_404(user_id)

    # Segurança: se for orientador de grupos, bloqueia exclusão para evitar FK.
    has_groups = Group.query.filter_by(orientador_user_id=user.id).first()
    if has_groups:
        flash("Não é possível excluir: usuário é orientador de um ou mais grupos. Altere os grupos antes.", "warning")
        return redirect(url_for("admin.users_list"))

    # Se preferir, faça “soft delete”: user.is_active = False; db.session.commit(); return.
    db.session.delete(user)
    db.session.commit()
    flash("Usuário excluído.", "success")
    return redirect(url_for("admin.users_list"))

# app/admin/routes.py
@admin_bp.route("/users/<int:user_id>/groups")
@login_required
@role_required("admin")
def users_groups(user_id):
    user = db.session.get(User, user_id)
    if not user:
        flash("Usuário não encontrado.", "warning")
        return redirect(url_for("admin.users_list"))

    role_val = (getattr(user, "role_value", None) or "").lower()
    # se sua model ainda usa Enum Role, descomente esta linha:
    # role_val = role_val or (user.role.name.lower() if user.role else "")

    if role_val != "professor":
        flash("Este usuário não é professor/orientador.", "warning")
        return redirect(url_for("admin.users_list"))

    groups = (Group.query
              .filter(Group.orientador_user_id == user.id)
              .order_by(Group.id.asc())
              .all())

    return render_template("admin/user_groups.html", user=user, groups=groups)
