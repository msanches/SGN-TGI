from decimal import Decimal
from io import StringIO, BytesIO
from datetime import datetime
from sqlalchemy.orm import joinedload

from flask import (
    Blueprint, render_template, request, redirect, url_for,
    flash, jsonify
)
from flask_login import login_required, current_user
from sqlalchemy import or_, func
from sqlalchemy.exc import IntegrityError

from ..extensions import db, bcrypt
from ..utils.decorators import role_required
from . import admin_bp
from ..services.excel_export import export_demo

from ..models import (
    Student, Campus, Offering,
    Group, GroupStudent, GroupProfessor,
    GroupAssessment, BannerEvaluation, Instrument,
    User, Role
)
from .forms import (
    StudentForm, GroupCreateForm, GroupEditForm, GradeForm, UserForm
)

from app.services.grades import upsert_assessment, get_assessment_score

# =============================================================================
# Helpers comuns
# =============================================================================

# --- Ofertas para o select do usuário (mostra dono atual quando não é o próprio) ---
def offering_choices_for_user(target_user_id: int | None = None):
    rows = (
        db.session.query(Offering.id, Offering.code, Offering.description,
                         Offering.professor_id, User.full_name)
        .outerjoin(User, User.id == Offering.professor_id)
        .order_by(Offering.code.asc())
        .all()
    )
    choices = []
    for oid, code, desc, owner_id, owner_name in rows:
        label = code
        if desc:
            label += f" — {desc}"
        if owner_id and (target_user_id is None or owner_id != target_user_id):
            label += f" (atual: {owner_name})"
        choices.append((oid, label))
    return choices



# routes.py (perto dos outros helpers)
def offering_choices_for_user(target_user_id: int | None = None):
    rows = (
        Offering.query
        .outerjoin(User, User.id == Offering.professor_id)
        .order_by(Offering.code.asc())
        .all()
    )
    choices = []
    for off in rows:
        owner = off.professor.full_name if off.professor else None
        label = f"{off.code}"
        if off.description:
            label += f" — {off.description}"
        if owner and (target_user_id is None or off.professor_id != target_user_id):
            label += f" (atual: {owner})"
        choices.append((off.id, label))
    return choices

def campus_choices():
    return [(c.id, c.name) for c in Campus.query.order_by(Campus.name.asc()).all()]

def professor_choices(include_placeholder=True):
    q = (
        User.query
        .filter(User.is_active.is_(True))
        .filter(or_(
            User.role == Role.professor,               # Enum(Role)
            func.lower(User.role) == "professor",      # string
            func.lower(User.role) == "role.professor"  # legado
        ))
        .order_by(User.full_name.asc())
    )
    rows = q.all()
    choices = [(-1, "— Sem orientador —")] if include_placeholder else []
    choices += [(u.id, u.full_name or u.email) for u in rows]
    return choices

def _inst(*names):
    """
    Resolve um membro de Instrument, tolerando variações de nomes.
    Ex.: _inst('RI','RELATORIO_I','relatorio_i')
    """
    for n in names:
        if hasattr(Instrument, n):
            return getattr(Instrument, n)
    return None

# Aliases tolerantes (aceitam siglas e nomes PT)
INST_RI    = _inst("RI", "RELATORIO_I", "relatorio_i")
INST_RII   = _inst("RII", "RELATORIO_II", "relatorio_ii")
INST_PAPER = _inst("PAPER", "paper")

# =============================================================================
# Dashboard / Export
# =============================================================================

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

# =============================================================================
# Students
# =============================================================================

@admin_bp.route("/students")
@login_required
@role_required("admin")
def students_list():
    q = (request.args.get("q") or "").strip()
    campus_id = (request.args.get("campus") or "").strip()
    off_id    = (request.args.get("off") or "").strip()

    query = (Student.query
             .options(joinedload(Student.campus), joinedload(Student.offering)))

    if q:
        like = f"%{q}%"
        query = query.filter(or_(Student.name.ilike(like), Student.rgm.ilike(like)))

    if campus_id.isdigit():
        query = query.filter(Student.campus_id == int(campus_id))

    if off_id.isdigit():
        query = query.filter(Student.offering_id == int(off_id))

    students  = query.order_by(Student.name.asc()).all()
    campuses  = Campus.query.order_by(Campus.name.asc()).all()
    offerings = Offering.query.order_by(Offering.code.asc()).all()

    return render_template(
        "admin/students_list.html",
        students=students,
        q=q,
        campus_id=campus_id,
        off_id=off_id,
        campuses=campuses,
        offerings=offerings,
    )

@admin_bp.route("/students/new", methods=["GET", "POST"])
@login_required
@role_required("admin")
def students_new():
    form = StudentForm()
    form.campus_id.choices = campus_choices()

    if form.validate_on_submit():
        campus = Campus.query.get(form.campus_id.data)
        if campus is None:
            flash("Campus inválido.", "danger")
            return render_template("admin/students_new.html", form=form)

        code = (form.offering.data or "").strip()
        offering = Offering.query.filter_by(code=code).first()
        if not offering:
            offering = Offering(code=code, description=None)
            db.session.add(offering)
            db.session.flush()

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
    db.session.delete(st)
    db.session.commit()
    flash("Aluno excluído.", "success")
    return redirect(url_for("admin.students_list"))

# =============================================================================
# Groups
# =============================================================================

@admin_bp.route("/groups")
@login_required
@role_required("admin")
def groups_list():
    q = (request.args.get("q") or "").strip()
    advisor = request.args.get("advisor", type=int)

    # base de grupos; vamos permitir filtrar por aluno e por orientador
    base = db.session.query(Group)

    # filtro por orientador
    if advisor:
        base = base.filter(Group.orientador_user_id == advisor)

    # filtro por aluno (nome ou RGM)
    if q:
        like = f"%{q}%"
        base = (base.join(GroupStudent, GroupStudent.group_id == Group.id, isouter=True)
                    .join(Student, Student.id == GroupStudent.student_id, isouter=True)
                    .filter((Student.name.ilike(like)) | (Student.rgm.ilike(like))))

    groups = base.order_by(Group.id.asc()).all()

    # carrega membros em lote (evita N+1; members é dynamic => fazemos manual)
    group_ids = [g.id for g in groups] or [0]
    rows_members = (
        db.session.query(GroupStudent.group_id, Student)
        .join(Student, Student.id == GroupStudent.student_id)
        .filter(GroupStudent.group_id.in_(group_ids))
        .order_by(Student.name.asc())
        .all()
    )
    members_map = {}
    for gid, st in rows_members:
        members_map.setdefault(gid, []).append(st)

    data = []
    for g in groups:
        orientador = g.orientador.full_name if g.orientador else None
        data.append({"g": g, "members": members_map.get(g.id, []), "orientador": orientador})

    # lista de orientadores para o select (ativos)
    advisors = (
        db.session.query(User.id, User.full_name)
        .filter((User.role == "professor") & (User.is_active.is_(True)))
        .order_by(User.full_name.asc())
        .all()
    )

    return render_template(
        "admin/groups_list.html",
        groups=data,
        q=q,
        advisor=advisor,
        advisors=advisors,
    )

@admin_bp.route("/groups/new", methods=["GET", "POST"])
@login_required
@role_required("admin")
def groups_new():
    form = GroupCreateForm()
    form.orientador_user_id.choices = professor_choices()

    if request.method == "GET":
        form.orientador_user_id.data = -1  # sentinel “Sem orientador”

    if form.validate_on_submit():
        lines = [ln.strip() for ln in (form.rgms.data or "").splitlines() if ln.strip()]
        students = Student.query.filter(Student.rgm.in_(lines)).all()
        found_rgms = {s.rgm for s in students}
        missing = [r for r in lines if r not in found_rgms]
        if missing:
            flash(f"RGM(s) não encontrados: {', '.join(missing)}", "danger")
            return render_template("admin/groups_new.html", form=form)

        grp = Group(title=(form.title.data or "").strip() or None)
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
            "campus": s.campus.name if s.campus else "-",
            "offering": s.offering.code if s.offering else "-",
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
    form.orientador_user_id.choices = professor_choices()

    if request.method == "GET":
        form.title.data = group.title or ""
        form.orientador_user_id.data = group.orientador_user_id if group.orientador_user_id is not None else -1
        current_rgms = [gs.student.rgm for gs in group.members]
        form.rgms.data = "\n".join(current_rgms)

    if form.validate_on_submit():
        group.title = (form.title.data or "").strip() or None
        sel = form.orientador_user_id.data
        group.orientador_user_id = None if sel == -1 else sel

        # Normaliza lista de RGMs desejados
        lines = [ln.strip() for ln in (form.rgms.data or "").splitlines() if ln.strip()]
        wanted_rgms = set(lines)

        # Resolve RGMs -> Students
        students = Student.query.filter(Student.rgm.in_(wanted_rgms)).all()
        found_by_rgm = {s.rgm: s for s in students}
        missing = [r for r in wanted_rgms if r not in found_by_rgm]
        if missing:
            flash(f"RGM(s) não encontrados: {', '.join(missing)}", "warning")

        wanted_ids = {found_by_rgm[r].id for r in found_by_rgm}
        current_ids = {gs.student_id for gs in group.members}

        # --- DETECÇÃO DE CONFLITOS (alunos já em outro grupo) ---
        # Se não estiver reatribuindo, apenas avisa e não toca nos dados
        reassign = (request.form.get("reassign") == "1")

        if wanted_ids:
            conflicts = (
                db.session.query(Student.id, Student.rgm, Student.name, Group.id, Group.title)
                .join(GroupStudent, GroupStudent.student_id == Student.id)
                .join(Group, Group.id == GroupStudent.group_id)
                .filter(Student.id.in_(wanted_ids), GroupStudent.group_id != group.id)
                .all()
            )
        else:
            conflicts = []

        if conflicts and not reassign:
            # Só informa o problema e retorna 409 sem alterar nada
            itens = [f"{rgm} - {name} (já no grupo #{gid}: '{gtitle}')" for sid, rgm, name, gid, gtitle in conflicts]
            flash(
                "Alguns alunos já pertencem a outro grupo e não foram adicionados:\n" +
                "".join(itens) +
                "\nDica: confirme a reatribuição marcando a opção",
                "warning"
            )
            # Recarrega a tela com membros atuais
            members = [gs.student for gs in group.members]
            current_rgms = [s.rgm for s in members]
            return render_template("admin/groups_edit.html",
                                   form=form, group=group, members=members, current_rgms=current_rgms), 409

        # --- A PARTIR DAQUI: APLICAR MUDANÇAS ---
        try:
            if conflicts and reassign:
                # Remove vínculos antigos dos conflitantes (move)
                conflict_ids = [sid for sid, *_ in conflicts]
                GroupStudent.query.filter(GroupStudent.student_id.in_(conflict_ids)).delete(synchronize_session=False)

            # Remover quem saiu deste grupo
            to_remove = current_ids - wanted_ids
            if to_remove:
                GroupStudent.query.filter(
                    GroupStudent.group_id == group.id,
                    GroupStudent.student_id.in_(list(to_remove))
                ).delete(synchronize_session=False)

            # Adicionar quem falta (evita duplicar quem já está)
            to_add = wanted_ids - (current_ids - set())  # current_ids já reflete antes das remoções
            for sid in to_add:
                db.session.add(GroupStudent(group_id=group.id, student_id=sid))

            db.session.commit()

            msg = "Grupo atualizado com sucesso."
            if conflicts and reassign:
                moved_rgms = ", ".join([rgm for _, rgm, *_ in conflicts])
                msg += f" Reatribuídos: {moved_rgms}."
            flash(msg, "success")
            return redirect(url_for("admin.groups_list"))

        except IntegrityError:
            db.session.rollback()
            # fallback defensivo: recalcula conflitos e avisa
            flash("Conflito de membros detectado. Nenhuma alteração foi aplicada.", "danger")
            members = [gs.student for gs in group.members]
            current_rgms = [s.rgm for s in members]
            return render_template("admin/groups_edit.html",
                                   form=form, group=group, members=members, current_rgms=current_rgms), 409

    # GET ou formulário inválido
    members = [gs.student for gs in group.members]
    current_rgms = [s.rgm for s in members]
    return render_template("admin/groups_edit.html",
                           form=form, group=group, members=members, current_rgms=current_rgms)


@admin_bp.route("/groups/<int:group_id>/delete", methods=["POST"])
@login_required
@role_required("admin")
def groups_delete(group_id):
    grp = Group.query.get_or_404(group_id)
    GroupStudent.query.filter_by(group_id=grp.id).delete()
    GroupProfessor.query.filter_by(group_id=grp.id).delete()
    GroupAssessment.query.filter_by(group_id=grp.id).delete()
    BannerEvaluation.query.filter_by(group_id=grp.id).delete()
    db.session.delete(grp)
    db.session.commit()
    flash("Grupo excluído.", "success")
    return redirect(url_for("admin.groups_list"))

# =============================================================================
# Notas do Grupo (Admin) — RI/RII como check (0.5), Paper 0..4
# =============================================================================

@admin_bp.route("/groups/<int:group_id>/grades", methods=["GET", "POST"])
@login_required
@role_required("admin")
def groups_grades(group_id):
    group = Group.query.get_or_404(group_id)
    form = GradeForm()

    if form.validate_on_submit():
        score_ri  = Decimal("0.5") if form.relatorio_i.data  else Decimal("0.0")
        score_rii = Decimal("0.5") if form.relatorio_ii.data else Decimal("0.0")
        paper_val = form.paper.data
        score_paper = Decimal(str(paper_val)) if paper_val is not None else Decimal("0.0")

        upsert_assessment(group.id, INST_RI,    score_ri,    current_user.id)
        upsert_assessment(group.id, INST_RII,   score_rii,   current_user.id)
        upsert_assessment(group.id, INST_PAPER, score_paper, current_user.id)

        db.session.commit()
        flash("Notas salvas com sucesso.", "success")
        return redirect(url_for("admin.groups_grades", group_id=group.id))

    # Pré-preenche
    ri_score    = get_assessment_score(group.id, INST_RI)    or Decimal("0")
    rii_score   = get_assessment_score(group.id, INST_RII)   or Decimal("0")
    paper_score = get_assessment_score(group.id, INST_PAPER)

    form.relatorio_i.data  = (ri_score  >= Decimal("0.5"))
    form.relatorio_ii.data = (rii_score >= Decimal("0.5"))
    form.paper.data = float(paper_score) if paper_score is not None else None

    members = [gs.student for gs in group.members]
    return render_template("admin/groups_grades.html", group=group, members=members, form=form)

# =============================================================================
# Users
# =============================================================================

@admin_bp.route("/users")
@login_required
@role_required("admin")
def users_list():
    q = (request.args.get("q") or "").strip()
    role_param = (request.args.get("role") or "").strip().lower()

    query = User.query
    if q:
        like = f"%{q}%"
        query = query.filter(or_(User.full_name.ilike(like), User.email.ilike(like)))

    # 🔧 filtro robusto por perfil
    aliases = {
        "admin": "admin",
        "professor": "professor",
        "convidado": "convidado",
        "guest": "convidado",   # trata sinônimo
    }
    if role_param in aliases:
        target = aliases[role_param]

        conds = [
            func.lower(User.role) == target,                 # coluna string normalizada
            func.lower(User.role) == f"role.{target}",       # dado legado "Role.professor"
        ]
        # se a coluna for Enum(Role), este comparador funciona
        try:
            conds.append(User.role == Role(target))
        except Exception:
            pass

        query = query.filter(or_(*conds))

    users = query.order_by(User.full_name.asc()).all()

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
    form.offerings.choices = offering_choices_for_user()

    if form.validate_on_submit():
        # e-mail único
        if User.query.filter_by(email=form.email.data.strip().lower()).first():
            flash("Já existe um usuário com este e-mail.", "warning")
            return render_template("admin/user_form.html", form=form, is_new=True)

        # normaliza role (ajuste para Enum(Role) se necessário)
        role_value = (form.role.data or "").strip().lower()

        user = User(
            full_name=form.full_name.data.strip(),
            email=form.email.data.strip().lower(),
            role=role_value,
            is_active=bool(form.is_active.data),
        )
        if form.password.data:
            if hasattr(user, "set_password"):
                user.set_password(form.password.data)
            else:
                user.password_hash = bcrypt.generate_password_hash(form.password.data).decode()

        db.session.add(user)
        db.session.flush()   # pega user.id

        selected_ids = set(form.offerings.data or [])
        reassign = request.form.get("reassign_offers") == "1"

        # Se perfil = professor, processa ofertas
        if role_value == "professor" and selected_ids:
            # conflitos: ofertas já têm outro responsável
            conflict_rows = (
                db.session.query(Offering.id, Offering.code, User.full_name)
                .join(User, User.id == Offering.professor_id)
                .filter(Offering.id.in_(selected_ids), Offering.professor_id != user.id)
                .all()
            )
            if conflict_rows and not reassign:
                itens = [f"{code} (atual: {owner})" for oid, code, owner in conflict_rows]
                flash(
                    "Algumas ofertas já possuem responsável e não foram atribuídas:<br>"
                    + "<br>".join(itens)
                    + "<br><small>Marque “Reatribuir ofertas que já têm responsável” para prosseguir.</small>",
                    "warning"
                )
                # mantém o user criado? Melhor não — desfaz e reexibe form.
                db.session.rollback()
                form.offerings.choices = offering_choices_for_user()  # recarrega rótulos
                return render_template("admin/user_form.html", form=form, is_new=True), 409

            # reatribui (ou atribui) todas as selecionadas para o novo usuário
            (Offering.query
                .filter(Offering.id.in_(list(selected_ids)))
                .update({Offering.professor_id: user.id}, synchronize_session=False))

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
    form.offerings.choices = offering_choices_for_user(user.id)

    # Pré-seleciona ofertas atuais
    if request.method == "GET":
        current_off_ids = [o.id for o in Offering.query.filter_by(professor_id=user.id).all()]
        form.offerings.data = current_off_ids

    if form.validate_on_submit():
        user.full_name = form.full_name.data.strip()
        user.email = form.email.data.strip().lower()
        user.is_active = bool(form.is_active.data)

        raw_role = (form.role.data or "").strip().lower()
        user.role = raw_role  # ajuste se usar Enum(Role)

        if form.password.data:
            if hasattr(user, "set_password"):
                user.set_password(form.password.data)
            else:
                user.password_hash = bcrypt.generate_password_hash(form.password.data).decode()

        selected_ids = set(form.offerings.data or [])
        reassign = request.form.get("reassign_offers") == "1"

        # Ofertas atualmente sob este usuário
        existing_ids = set(
            oid for (oid,) in db.session.query(Offering.id)
            .filter(Offering.professor_id == user.id).all()
        )

        # Se deixou de ser professor, desvincula tudo
        if raw_role != "professor":
            if existing_ids:
                (Offering.query
                    .filter(Offering.id.in_(list(existing_ids)))
                    .update({Offering.professor_id: None}, synchronize_session=False))
            selected_ids = set()  # ignora seleções
        else:
            # Conflitos: selecionadas que já pertencem a outro professor
            if selected_ids:
                conflict_rows = (
                    db.session.query(Offering.id, Offering.code, User.full_name, Offering.professor_id)
                    .join(User, User.id == Offering.professor_id)
                    .filter(Offering.id.in_(selected_ids),
                            Offering.professor_id.isnot(None),
                            Offering.professor_id != user.id)
                    .all()
                )
            else:
                conflict_rows = []

            if conflict_rows and not reassign:
                itens = [f"{code} (atual: {owner})" for oid, code, owner, _ in conflict_rows]
                flash(
                    "Algumas ofertas já possuem responsável e não foram atribuídas:<br>"
                    + "<br>".join(itens)
                    + "<br><small>Marque “Reatribuir ofertas que já têm responsável” para prosseguir.</small>",
                    "warning"
                )
                # re-renderiza mantendo escolhas do usuário
                form.offerings.choices = offering_choices_for_user(user.id)
                return render_template("admin/user_form.html", form=form, is_new=False), 409

            # sincroniza conjuntos
            to_add = selected_ids - existing_ids
            to_remove = existing_ids - selected_ids

            if to_add:
                (Offering.query
                    .filter(Offering.id.in_(list(to_add)))
                    .update({Offering.professor_id: user.id}, synchronize_session=False))

            if to_remove:
                (Offering.query
                    .filter(Offering.id.in_(list(to_remove)))
                    .update({Offering.professor_id: None}, synchronize_session=False))

        db.session.commit()

        if raw_role != "professor":
            flash("Usuário atualizado. Ofertas desvinculadas (perfil não é Professor).", "success")
        else:
            if request.form.get("reassign_offers") == "1":
                flash("Usuário e ofertas atualizados (reatribuição aplicada).", "success")
            else:
                flash("Usuário e ofertas atualizados.", "success")

        return redirect(url_for("admin.users_list"))

    return render_template("admin/user_form.html", form=form, is_new=False)


@admin_bp.route("/users/<int:user_id>/delete", methods=["POST"])
@login_required
@role_required("admin")
def users_delete(user_id):
    user = User.query.get_or_404(user_id)

    # Segurança: bloqueia exclusão se for orientador de grupos
    has_groups = Group.query.filter_by(orientador_user_id=user.id).first()
    if has_groups:
        flash("Não é possível excluir: usuário é orientador de um ou mais grupos. Altere os grupos antes.", "warning")
        return redirect(url_for("admin.users_list"))

    db.session.delete(user)
    db.session.commit()
    flash("Usuário excluído.", "success")
    return redirect(url_for("admin.users_list"))

@admin_bp.route("/users/<int:user_id>/groups")
@login_required
@role_required("admin")
def users_groups(user_id):
    user = db.session.get(User, user_id)
    if not user:
        flash("Usuário não encontrado.", "warning")
        return redirect(url_for("admin.users_list"))

    role_val = (
        getattr(user, "role_value", None)
        or (user.role.name if hasattr(user.role, "name") else user.role)
        or ""
    )
    if str(role_val).lower() != "professor":
        flash("Este usuário não é professor/orientador.", "warning")
        return redirect(url_for("admin.users_list"))

    groups = (
        Group.query
        .filter(Group.orientador_user_id == user.id)
        .order_by(Group.id.asc())
        .all()
    )

    return render_template("admin/user_groups.html", user=user, groups=groups)
