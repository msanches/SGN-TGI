from flask import render_template, request, redirect, url_for, flash, abort
from flask_login import login_required, current_user
from sqlalchemy import or_
from ..utils.decorators import role_required
from ..extensions import db
#from ..models import Group, GroupStudent, Student, Offering, GroupAssessment, Instrument, User  # <-- Instrument aqui!
from . import professors_bp
from .forms import GradeForm
from sqlalchemy.exc import IntegrityError
from collections import defaultdict
from ..models import Instrument  # garanta o import
from sqlalchemy import func
from io import BytesIO
import csv, io, datetime
from sqlalchemy import func
from flask import send_file
from ..models import Group, GroupStudent, Student, Offering, Campus, User, GroupAssessment, Instrument


def _ensure_owns_group(group_id: int) -> Group:
    g = Group.query.get_or_404(group_id)
    if g.orientador_user_id != current_user.id:
        abort(403)
    return g

def _fmt(n):
    """Formata nota com 2 casas e vírgula; vazio se None."""
    if n is None:
        return ""
    try:
        return f"{float(n):.2f}".replace(".", ",")
    except Exception:
        return str(n)

def _assessments_by_instrument(group_id: int):
    rows = GroupAssessment.query.filter_by(group_id=group_id).all()
    # chave = Enum Instrument; valor = linha
    return {row.instrument: row for row in rows}

def _upsert_grade(group_id: int, instrument, score):
    """
    Upsert de uma nota (0–10) para um instrumento específico.
    Se 'score' for None -> remove a linha daquele instrumento.
    """
    row = GroupAssessment.query.filter_by(group_id=group_id, instrument=instrument).first()
    if score is None:
        if row:
            db.session.delete(row)
        return
    # score preenchido -> cria/atualiza
    if row:
        row.score = score
        row.entered_by_user_id = current_user.id
    else:
        db.session.add(GroupAssessment(
            group_id=group_id,
            instrument=instrument,
            score=score,
            entered_by_user_id=current_user.id
        ))
#se der erro dá um crtrl z

@professors_bp.route("/")
@login_required
@role_required("professor")
def dashboard():
    # Meus grupos (como já estava)
    groups = (Group.query
              .filter_by(orientador_user_id=current_user.id)
              .order_by(Group.id.asc())
              .all())

    group_ids = [g.id for g in groups] or [0]
    rows = GroupAssessment.query.filter(
        GroupAssessment.group_id.in_(group_ids)
    ).all()
    scores = {gid: {"ri": None, "rii": None, "paper": None} for gid in group_ids}
    for r in rows:
        if r.instrument == Instrument.RELATORIO_I:
            scores[r.group_id]["ri"] = r.score
        elif r.instrument == Instrument.RELATORIO_II:
            scores[r.group_id]["rii"] = r.score
        elif r.instrument == Instrument.PAPER:
            scores[r.group_id]["paper"] = r.score

    # Minhas ofertas (sou o responsável)
    my_offerings = (Offering.query
                    .filter(Offering.professor_id == current_user.id)
                    .order_by(Offering.code.asc())
                    .all())

    return render_template("professors/dashboard.html",
                           groups=groups, scores=scores,
                           my_offerings=my_offerings)

@professors_bp.route("/groups")
@login_required
@role_required("professor")
def groups_list():
    q = (request.args.get("q") or "").strip()
    base = Group.query.filter_by(orientador_user_id=current_user.id)

    if q:
        base = (
            base.outerjoin(GroupStudent, GroupStudent.group_id == Group.id)
                .outerjoin(Student, Student.id == GroupStudent.student_id)
                .outerjoin(Offering, Offering.id == Student.offering_id)
                .filter(
                    or_(
                        Group.title.ilike(f"%{q}%"),
                        Student.name.ilike(f"%{q}%"),
                        Student.rgm.ilike(f"%{q}%"),
                        Offering.code.ilike(f"%{q}%"),
                    )
                )
                .distinct()
        )

    groups = base.order_by(Group.id.asc()).all()
    return render_template("professors/groups_list.html", groups=groups, q=q)

@professors_bp.route("/groups/<int:group_id>")
@login_required
@role_required("professor")
def group_detail(group_id):
    g = _ensure_owns_group(group_id)

    students = (Student.query
                .join(GroupStudent, GroupStudent.student_id == Student.id)
                .filter(GroupStudent.group_id == g.id)
                .order_by(Student.name.asc())
                .all())

    by_inst = _assessments_by_instrument(g.id)
    ri  = by_inst.get(Instrument.RELATORIO_I)
    rii = by_inst.get(Instrument.RELATORIO_II)
    pp  = by_inst.get(Instrument.PAPER)

    return render_template("professors/group_detail.html",
                           group=g, students=students,
                           ri=ri, rii=rii, paper=pp)


@professors_bp.route("/groups/<int:group_id>/grades", methods=["GET", "POST"])
@login_required
@role_required("professor")
def group_grades_edit(group_id):
    """Editar notas (Relatório I/II/Paper) do grupo do próprio professor (1 linha por instrumento)."""
    g = _ensure_owns_group(group_id)

    # leitura atual para pré-preencher
    by_inst = _assessments_by_instrument(g.id)

    # instancia o form com dados atuais
    form = GradeForm()
    if request.method == "GET":
        ri = by_inst.get(Instrument.RELATORIO_I)
        rii = by_inst.get(Instrument.RELATORIO_II)
        pp = by_inst.get(Instrument.PAPER)
        # WTForms DecimalField aceita float/str
        form.relatorio_i.data = float(ri.score) if ri else None
        form.relatorio_ii.data = float(rii.score) if rii else None
        form.paper.data = float(pp.score) if pp else None

    if form.validate_on_submit():
        try:
            _upsert_grade(g.id, Instrument.RELATORIO_I, form.relatorio_i.data)
            _upsert_grade(g.id, Instrument.RELATORIO_II, form.relatorio_ii.data)
            _upsert_grade(g.id, Instrument.PAPER,        form.paper.data)
            db.session.commit()
            flash("Notas salvas com sucesso.", "success")
            return redirect(url_for("professors.group_detail", group_id=g.id))
        except IntegrityError as e:
            db.session.rollback()
            flash("Erro ao salvar notas. Verifique os valores e tente novamente.", "danger")
            # opcional: logar e

    return render_template("professors/grades_edit.html", group=g, form=form)

#para exportar a lista de alunos da oferta
@professors_bp.route("/export/offerings/<int:offering_id>.csv")
@login_required
@role_required("professor")
def export_offering_csv(offering_id):
    """
    Exporta CSV com: Nº Grupo, RGM, Aluno, Campus, Oferta, Orientador, RI, RII, Paper, Banner (média)
    para TODOS os alunos da oferta (independente do orientador).
    """
    off = _offering_guard(offering_id)

    # Alunos da oferta + (grupo, orientador) se houver
    q = (
        db.session.query(
            Student.id.label("student_id"),
            Student.rgm,
            Student.name.label("aluno"),
            Offering.code.label("oferta"),
            Campus.name.label("campus"),
            Group.id.label("grupo_id"),
            User.full_name.label("orientador"),
        )
        .select_from(Student)
        .join(Offering, Offering.id == Student.offering_id)
        .outerjoin(Campus, Campus.id == Student.campus_id)
        .outerjoin(GroupStudent, GroupStudent.student_id == Student.id)
        .outerjoin(Group, Group.id == GroupStudent.group_id)
        .outerjoin(User, User.id == Group.orientador_user_id)
        .filter(Student.offering_id == off.id)
        .order_by(Group.id.asc(), Student.name.asc())
    )
    rows = q.all()

    group_ids = [r.grupo_id for r in rows if r.grupo_id] or [0]

    # Notas por grupo/instrumento (AVG para banner; para RI/RII/Paper avg == valor)
    ga = (
        db.session.query(
            GroupAssessment.group_id.label("gid"),
            GroupAssessment.instrument.label("inst"),
            func.avg(GroupAssessment.score).label("nota"),
        )
        .filter(GroupAssessment.group_id.in_(group_ids))
        .group_by(GroupAssessment.group_id, GroupAssessment.instrument)
        .all()
    )

    notas = {gid: {"ri": None, "rii": None, "paper": None, "banner": None} for gid in group_ids}
    for r in ga:
        if r.inst == Instrument.RELATORIO_I:
            notas[r.gid]["ri"] = r.nota
        elif r.inst == Instrument.RELATORIO_II:
            notas[r.gid]["rii"] = r.nota
        elif r.inst == Instrument.PAPER:
            notas[r.gid]["paper"] = r.nota
        elif hasattr(Instrument, "BANNER") and r.inst == Instrument.BANNER:
            notas[r.gid]["banner"] = r.nota

    # Gera CSV (delimitador ';', BOM UTF-8 para Excel)
    sio = io.StringIO(newline="")
    wr = csv.writer(sio, delimiter=";")
    wr.writerow(["Nº Grupo", "RGM", "Aluno", "Campus", "Oferta", "Orientador",
                 "RI", "RII", "Paper", "Banner (média)"])

    for r in rows:
        g = r.grupo_id
        ns = notas.get(g, {}) if g else {}
        wr.writerow([
            g or "",
            r.rgm,
            r.aluno,
            r.campus or "",
            r.oferta,
            r.orientador or "",
            _fmt(ns.get("ri")),
            _fmt(ns.get("rii")),
            _fmt(ns.get("paper")),
            _fmt(ns.get("banner")),
        ])

    data = sio.getvalue().encode("utf-8-sig")  # BOM para Excel/PT-BR
    bio = BytesIO(data)
    ts = datetime.datetime.now().strftime("%Y%m%d-%H%M")
    fname = f"notas_oferta_{off.code}_{ts}.csv"
    return send_file(
        bio,
        mimetype="text/csv",
        as_attachment=True,
        download_name=fname,
    )