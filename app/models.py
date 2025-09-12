import re, hashlib
from werkzeug.security import generate_password_hash as wz_generate_password_hash, check_password_hash as wz_check_password_hash
from .extensions import db, bcrypt
from flask_login import UserMixin
from sqlalchemy import Enum, CheckConstraint, UniqueConstraint, func
from enum import Enum as PyEnum

class Role(PyEnum):
    admin = "admin"
    professor = "professor"
    convidado = "convidado"

class Instrument(PyEnum):
    RELATORIO_I = "RELATORIO_I"
    RELATORIO_II = "RELATORIO_II"
    PAPER = "PAPER"

class User(UserMixin, db.Model):
    # ...
    password_hash = db.Column(db.String(255), nullable=False)
    # ...
    __tablename__ = "users"
    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    email = db.Column(db.String(190), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    full_name = db.Column(db.String(150), nullable=False)
    role = db.Column(Enum(Role), nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, server_default=func.now())
    updated_at = db.Column(db.DateTime, server_default=func.now(), onupdate=func.now())

    # role pode ser string ('admin' | 'professor' | 'guest') ou Enum(Role)
    role = db.Column(db.String(20), nullable=False, default="guest")

    @property
    def role_value(self) -> str:
        """Retorna 'admin' | 'professor' | 'guest' mesmo que self.role seja Enum."""
        rv = getattr(self, "role", None)
        # se for Enum(Role), pega .value
        if rv is not None and hasattr(rv, "value"):
            return (rv.value or "guest").lower()
        # se for string
        if isinstance(rv, str):
            return (rv or "guest").lower()
        return "guest"

    @property
    def is_admin(self) -> bool:
        return self.role_value == "admin"

    @property
    def is_professor(self) -> bool:
        return self.role_value == "professor"

    def set_password(self, password: str, method: str = "bcrypt"):
        """
        Gera e armazena o hash da senha.
        method:
          - "bcrypt" (padrão): usa flask-bcrypt
          - "pbkdf2:sha256[:iteracoes]": usa Werkzeug (ex.: "pbkdf2:sha256:260000")
        """
        if method and method.startswith("pbkdf2"):
            self.password_hash = wz_generate_password_hash(password, method=method)
        else:
            self.password_hash = bcrypt.generate_password_hash(password).decode("utf-8")

    def check_password(self, password: str) -> bool:
        """
        Verifica a senha aceitando:
          - PBKDF2 (padrão Werkzeug, base64)
          - PBKDF2 no formato legado HEX (gerado no primeiro script)
          - bcrypt (flask-bcrypt)
        """
        ph = (self.password_hash or "").strip()
        if not ph:
            return False

        # --- PBKDF2 (tanto base64 quanto o nosso formato HEX legado) ---
        if ph.startswith("pbkdf2:"):
            try:
                # Formato: pbkdf2:sha256:ITER$SALT$HASH
                parts = ph.split("$")
                if len(parts) == 3:
                    method_part, salt_str, stored = parts
                    # extrai iterações (ex.: "pbkdf2:sha256:260000")
                    iters = 260000
                    mparts = method_part.split(":")
                    if len(mparts) >= 3 and mparts[2].isdigit():
                        iters = int(mparts[2])

                    # Caso legado: SALT e HASH em HEX
                    if re.fullmatch(r"[0-9a-fA-F]+", salt_str) and re.fullmatch(r"[0-9a-fA-F]+", stored):
                        dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), bytes.fromhex(salt_str), iters)
                        return dk.hex() == stored

                # Caso padrão (Werkzeug, base64)
                return wz_check_password_hash(ph, password)
            except Exception:
                return False

        # --- bcrypt ---
        try:
            return bcrypt.check_password_hash(ph, password)
        except Exception:
            # Fallback: tenta Werkzeug por via das dúvidas
            try:
                return wz_check_password_hash(ph, password)
            except Exception:
                return False

class Campus(db.Model):
    __tablename__ = "campuses"
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(120), unique=True, nullable=False)

class Offering(db.Model):
    __tablename__ = "offerings"  # ajuste se necessário
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(50), unique=True, nullable=False)
    description = db.Column(db.String(255))
    # NOVO: dono da oferta (professor responsável)
    professor_id = db.Column(db.BigInteger, db.ForeignKey("users.id"), nullable=True, index=True)
    professor = db.relationship("User", foreign_keys=[professor_id])


class Student(db.Model):
    __tablename__ = "students"
    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    rgm = db.Column(db.String(30), unique=True, nullable=False)
    name = db.Column(db.String(150), nullable=False)
    campus_id = db.Column(db.Integer, db.ForeignKey("campuses.id"), nullable=False)
    offering_id = db.Column(db.Integer, db.ForeignKey("offerings.id"), nullable=False)
    created_at = db.Column(db.DateTime, server_default=func.now())
    updated_at = db.Column(db.DateTime, server_default=func.now(), onupdate=func.now())

    campus = db.relationship("Campus")
    offering = db.relationship("Offering")

class Group(db.Model):
    __tablename__ = "tgi_groups"  # evita conflito com palavra reservada
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)  # Nº do grupo
    title = db.Column(db.String(200), nullable=False)  # <-- NOVO
    orientador_user_id = db.Column(db.BigInteger, db.ForeignKey("users.id"))
    created_at = db.Column(db.DateTime, server_default=func.now())
    updated_at = db.Column(db.DateTime, server_default=func.now(), onupdate=func.now())

    orientador = db.relationship("User")

class GroupStudent(db.Model):
    __tablename__ = "group_students"
    group_id = db.Column(db.Integer, db.ForeignKey("tgi_groups.id"), primary_key=True)
    student_id = db.Column(db.BigInteger, db.ForeignKey("students.id"), primary_key=True)

    __table_args__ = (
        UniqueConstraint("student_id", name="uq_student_single_group"),
    )

    group = db.relationship("Group", backref=db.backref("members", lazy="dynamic"))
    student = db.relationship("Student")

class GroupProfessor(db.Model):
    __tablename__ = "group_professors"
    group_id = db.Column(db.Integer, db.ForeignKey("tgi_groups.id"), primary_key=True)
    user_id = db.Column(db.BigInteger, db.ForeignKey("users.id"), primary_key=True)
    role_in_group = db.Column(db.Enum("ORIENTADOR","AVALIADOR","COORIENTADOR", name="role_in_group_enum"), default="AVALIADOR")

    group = db.relationship("Group", backref=db.backref("professors", lazy="dynamic"))
    user = db.relationship("User")

class GroupAssessment(db.Model):
    __tablename__ = "group_assessments"
    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    group_id = db.Column(db.Integer, db.ForeignKey("tgi_groups.id"), nullable=False)
    instrument = db.Column(Enum(Instrument), nullable=False)
    score = db.Column(db.Numeric(5,2), nullable=False)
    entered_by_user_id = db.Column(db.BigInteger, db.ForeignKey("users.id"), nullable=False)
    entered_at = db.Column(db.DateTime, server_default=func.now())

    __table_args__ = (
        UniqueConstraint("group_id", "instrument", name="uq_group_instrument"),
        CheckConstraint("score >= 0 AND score <= 10", name="ck_score_range"),
    )

    group = db.relationship("Group")
    user = db.relationship("User")

class BannerEvaluation(db.Model):
    __tablename__ = "banner_evaluations"
    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    group_id = db.Column(db.Integer, db.ForeignKey("tgi_groups.id"), nullable=False)
    evaluator_user_id = db.Column(db.BigInteger, db.ForeignKey("users.id"), nullable=False)
    score = db.Column(db.Numeric(5,2), nullable=False)
    comments = db.Column(db.Text)
    entered_at = db.Column(db.DateTime, server_default=func.now())

    __table_args__ = (
        UniqueConstraint("group_id", "evaluator_user_id", name="uq_banner_once"),
        CheckConstraint("score >= 0 AND score <= 5", name="ck_banner_score_range"),
    )

    group = db.relationship("Group")
    evaluator = db.relationship("User")
