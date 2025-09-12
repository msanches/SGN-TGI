from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, BooleanField, SubmitField
from wtforms.validators import DataRequired, Email, Length, EqualTo, Optional

class LoginForm(FlaskForm):
    email = StringField("Email", validators=[DataRequired(), Email(), Length(max=190)])
    password = PasswordField("Senha", validators=[DataRequired(), Length(min=6, max=128)])
    remember = BooleanField("Lembrar")
    submit = SubmitField("Entrar")

class AccountForm(FlaskForm):
    full_name = StringField("Nome completo", validators=[DataRequired(), Length(max=150)])
    email = StringField("Email", validators=[DataRequired(), Email(), Length(max=190)])
    current_password = PasswordField("Senha atual", validators=[Optional(), Length(min=6, max=128)])
    new_password = PasswordField("Nova senha", validators=[Optional(), Length(min=6, max=128)])
    confirm_new_password = PasswordField(
        "Confirmar nova senha",
        validators=[Optional(), EqualTo("new_password", message="As senhas não conferem")]
    )
    submit = SubmitField("Salvar alterações")
