"""Whitespace cannot establish that an applicant filled a required input."""
from demo.backend import generic_programs, models
from demo.backend.tests.test_generic_programs import client, fill, publish, start


def test_whitespace_only_required_text_blocks_submit_and_pass_review(client):
    posting = publish(client)
    row, _form, layout = start(client, posting)
    fill(client, row, layout)
    endpoint = f'/api/applications/{row["id"]}'
    assert client.get(endpoint + '/final-check').json()['can_submit']
    required_text = next(key for key, field in layout['fields'].items()
                         if field.get('required') and not field.get('readonly')
                         and field.get('field_type') == 'text')
    for blank in ('   ', '\t\n', '\u00a0'):
        response = client.patch(endpoint, json={'form1': {required_text: blank}})
        assert response.status_code == 200, response.text
        checked = client.get(endpoint + '/final-check').json()
        assert not checked['can_submit']
        assert any(item['target'] == required_text for item in checked['blockers'])
        assert client.post(endpoint + '/submit').status_code == 400
        with models.get_session() as session:
            saved = session.get(models.Application, row['id'])
            assert generic_programs.run_review(saved).final_status == 'NEEDS_REVIEW'
