from flask_wtf import FlaskForm
from wtforms import BooleanField, DecimalField, SubmitField
from wtforms.validators import Optional, NumberRange

def comma_to_dot(value):
    if value is None:
        return None
    if isinstance(value, str):
        v = value.strip()
        if not v:
            return None
        return v.replace(",", ".")
    return value

class GradeForm(FlaskForm):
    relatorio_i  = BooleanField("Relatório I (0,5)")
    relatorio_ii = BooleanField("Relatório II (0,5)")
    paper        = DecimalField("Paper (0 a 4)", places=2,
                                validators=[Optional(), NumberRange(min=0, max=4)])
    submit       = SubmitField("Salvar")