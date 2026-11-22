"""Explicit current-version bodies for legacy synthetic API scenario tests."""
from sqlmodel import select
from demo.backend import models


def decision_precondition(path, payload):
    body=dict(payload)
    with models.get_session() as session:
        if path.endswith('/decisions'):
            ids=body.get('application_ids',[])
            rows=session.exec(select(models.Review).where(models.Review.application_id.in_(ids))).all()
            body['expected_revisions']={str(row.application_id):row.revision for row in rows}
        else:
            aid=int(path.rsplit('/',2)[1])
            row=session.exec(select(models.Review).where(models.Review.application_id==aid)).first()
            if row is not None:body['expected_revision']=row.revision
    return body
