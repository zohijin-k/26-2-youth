"""Optional officer text drafts with server-owned public and rule-code inputs."""
from typing import Any
from fastapi import Query
import pymupdf
from .. import llm_drafts
from . import officer, postings, posting_workspace
from .common import load_application


@postings.officer_router.post('/{posting_id}/workspace/guidance-draft')
def guidance_draft(posting_id: int) -> dict[str, str]:
    posting = postings._load(posting_id)
    posting_workspace.editable(posting)
    catalog = posting_workspace.slot_catalog()
    types = [catalog[key].doc_type for key in (posting.template_json or {}).get('required_docs',[]) if key in catalog]
    notice = postings._stored_file(posting,'notice')
    public_text = ''
    if notice:
        with pymupdf.open(notice) as pdf:
            for page in pdf:
                public_text += page.get_text()
                if len(public_text) >= llm_drafts.MAX_NOTICE_CHARACTERS:
                    break
    return llm_drafts.draft_guidance({'title':posting.title, 'apply_start':posting.apply_start,
        'apply_end':posting.apply_end}, types, public_text)


@officer.router.get('/applications/{application_id}/reason-explanation')
def reason_explanation(application_id: int, role: str = Query('province')) -> dict[str, str]:
    reasons = officer.review_reasons(application_id,role)
    codes = [finding.get('code') for doc in reasons['documents'] for finding in doc['findings'] if isinstance(finding,dict)]
    if reasons['missing']: codes.append('MISSING_DOCUMENT')
    if load_application(application_id).program_code.startswith('posting_'):
        codes.append('PROGRAM_RULES_UNSET')
    return llm_drafts.draft_review(codes)
