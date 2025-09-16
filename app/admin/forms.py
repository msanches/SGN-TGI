from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, SubmitField, SelectField, DecimalField, HiddenField
from wtforms.validators import DataRequired, Length, Optional, NumberRange

# app/auth/forms.py ou app/admin/forms.py (onde está seu GroupEditForm)
from wtforms import SelectField, StringField, TextAreaField, SubmitField
from wtforms.validators import Optional, Length
from wtforms import StringField, TextAreaField, SelectField, SubmitField
from wtforms import BooleanField, DecimalField, SubmitField
from wtforms.validators import Optional, NumberRange
from wtforms import StringField, SelectField, BooleanField, PasswordField, SelectMultipleField

from wtforms import StringField, SelectField, BooleanField, PasswordField, SubmitField
from wtforms.validators import DataRequired, Email, Optional, Length

class UserForm(FlaskForm):
    full_name = StringField("Nome completo", validators=[DataRequired(), Length(max=120)])
    email = StringField("E-mail", validators=[DataRequired(), Email(), Length(max=255)])
    role = SelectField(
        "Perfil",
        choices=[("admin", "Admin"), ("professor", "Professor/Orientador"), ("guest", "Convidado")],
        validators=[DataRequired()],
        coerce=str,   # <- importante
    )
    is_active = BooleanField("Ativo", default=True)
    password = PasswordField("Definir / Trocar senha", validators=[Optional(), Length(min=6, max=128)])
    offerings = SelectMultipleField("Ofertas (responsável)", coerce=int, choices=[])
    submit = SubmitField("Salvar")

class StudentForm(FlaskForm):
    name = StringField("Nome do aluno", validators=[DataRequired(), Length(max=150)])
    rgm = StringField("RGM", validators=[DataRequired(), Length(max=30)])
    #campus = StringField("Campus", validators=[DataRequired(), Length(max=120)])
    campus_id = SelectField("Campus", coerce=int, validators=[DataRequired()])
    offering = StringField("Oferta", validators=[DataRequired(), Length(max=60)])
    submit = SubmitField("Salvar")

class GroupCreateForm(FlaskForm):
    title = StringField("Título do projeto", validators=[Optional(), Length(max=255)])
    orientador_user_id = SelectField("Orientador", coerce=int, validators=[Optional()])
    rgms = TextAreaField("RGMs (um por linha)", validators=[Optional()])
    submit = SubmitField("Criar")

class GroupEditForm(FlaskForm):
    title = StringField("Título do projeto", validators=[Optional(), Length(max=255)])
    orientador_user_id = SelectField("Orientador", coerce=int, validators=[Optional()])
    rgms = TextAreaField("RGMs (um por linha)", validators=[Optional()])
    submit = SubmitField("Salvar")

class GradeForm(FlaskForm):
    relatorio_i = BooleanField("Relatório II (0,5)")
    relatorio_ii = BooleanField("Relatório II (0,5)")
    paper        = DecimalField("Paper (0 a 4)", places=2,
                                validators=[Optional(), NumberRange(min=0, max=4)])
    submit       = SubmitField("Salvar")
