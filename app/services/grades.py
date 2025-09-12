from decimal import Decimal
from app.models import GroupAssessment, Instrument
from app.extensions import db

def upsert_assessment(group_id, instrument, score, user_id):
    ga = GroupAssessment.query.filter_by(group_id=group_id, instrument=instrument).first()
    if ga:
        ga.score = Decimal(str(score))
        ga.entered_by_user_id = user_id
    else:
        ga = GroupAssessment(
            group_id=group_id,
            instrument=instrument,
            score=Decimal(str(score)),
            entered_by_user_id=user_id
        )
        db.session.add(ga)
    return ga

def get_assessment_score(group_id, instrument):
    ga = GroupAssessment.query.filter_by(group_id=group_id, instrument=instrument).first()
    return ga.score if ga else None
