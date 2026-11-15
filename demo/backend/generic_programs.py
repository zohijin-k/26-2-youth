"""Application-frozen runtime for officer-published programs.

Built-in programs continue through their existing rules and forms. Generic
programs reuse document checks and PDF rendering, with no invented eligibility.
"""
from __future__ import annotations

import base64
from copy import deepcopy
from dataclasses import asdict, replace
from datetime import date, datetime
from pathlib import Path
import re
import shutil
from typing import Any

from fastapi import HTTPException
from fastapi.responses import Response
import pymupdf
from sqlmodel import select

from engine_v2.pipeline.privacy import mask_data
from .forms.coords import FormCoords
from .forms.values import FilledForm
from .forms.render import render, render_page_png
from .models import Application, ProgramApplicationSnapshot, ProgramPosting, Review, get_session
from .rules.doc_types import DocType
from .rules.programs import get_program as builtin_program
from .rules.required_docs import DocRequirement

NOTICE = '자격 규칙 미설정 — 담당자가 공고문 기준으로 확인'
_CODE = re.compile(r'posting_([1-9]\d{0,17})\Z')


def is_generic(value: Any) -> bool:
    return isinstance(value, str) and _CODE.fullmatch(value) is not None


def storage() -> Path:
    from .api import common
    return common.STORAGE


def snapshot(app: Application) -> ProgramApplicationSnapshot:
    with get_session() as session:
        row = session.get(ProgramApplicationSnapshot, app.id)
    if row is None:
        raise HTTPException(409, '신청 사업의 확정 서식 정보를 찾을 수 없습니다.')
    return row


def program(code: str):
    if not is_generic(code):
        return builtin_program(code)
    with get_session() as session:
        posting = session.get(ProgramPosting, int(code.removeprefix('posting_')))
        saved = session.exec(select(ProgramApplicationSnapshot).where(ProgramApplicationSnapshot.posting_id == int(code.removeprefix('posting_')))).first() if posting is None else None
    raw = saved.snapshot_json if saved else {}
    if posting is None and not raw:
        raise ValueError('사업을 찾을 수 없습니다.')
    return replace(builtin_program('job_package'), code=code,
        name=posting.title if posting else raw['title'], selection='manual',
        has_subsidy_items=False, has_income_requirement=False, has_work_requirement=False,
        supplement_days=None, total_quota=None, quota_by_region=None,
        required_form_fields=(),summary_fields=(),consent_types=(),
        apply_period=(posting.apply_start, posting.apply_end) if posting else (date.fromisoformat(raw['apply_start']),date.fromisoformat(raw['apply_end'])))


def eligible_posting(code: str) -> ProgramPosting:
    from .api import postings, posting_workspace, posting_workflow
    if not is_generic(code):
        raise HTTPException(404, '사업을 찾을 수 없습니다.')
    row = postings._load(int(code.removeprefix('posting_')))
    if not posting_workspace.managed(row) or row.status != 'published' or postings.phase_of(row,postings._today()) != 'open' or posting_workflow.publish_blockers(row):
        raise HTTPException(409, '접수 중이며 서식 틀이 확정된 사업만 신청할 수 있습니다.')
    return row


def freeze(session: Any, app: Application, posting: ProgramPosting) -> None:
    from .api import posting_workspace
    root = storage() / 'program_snapshots' / str(app.id)
    root.mkdir(parents=True,exist_ok=True)
    entries = []
    try:
        for row in posting_workspace.form_rows(posting.id or 0):
            fields = {}
            groups = {}
            for index, (_, original) in enumerate((row.layout_json or {})['fields'].items()):
                key = f'p{row.id}_f{index:04d}'
                field = deepcopy(original)
                group = field.get('group')
                if group:
                    groups.setdefault(group,f'p{row.id}_g{len(groups):04d}')
                    field['group'] = groups[group]
                fields[key] = field
            target = root / f'form-{row.id}.pdf'
            shutil.copyfile(posting_workspace.form_path(row),target)
            entries.append({'form_no':f'program_form_{row.id}','title':row.file_name,
                'path':str(target.relative_to(storage())), 'fields':fields,
                'page_sizes':deepcopy(row.layout_json['page_sizes'])})
        requirements=[]
        catalog=posting_workspace.slot_catalog()
        for key in (posting.template_json or {}).get('required_docs',[]):
            req=asdict(catalog[key])
            for attr in ('min_issue_date','max_issue_date'):
                if isinstance(req.get(attr),date): req[attr]=req[attr].isoformat()
            requirements.append(req)
        session.add(ProgramApplicationSnapshot(application_id=app.id,posting_id=posting.id,
            snapshot_json={'title':posting.title,'apply_start':posting.apply_start.isoformat(),
                'apply_end':posting.apply_end.isoformat(),'guidance_text':posting.guidance_text,
                'forms':entries,'requirements':requirements}))
    except Exception:
        shutil.rmtree(root,ignore_errors=True)
        raise


def forms(app: Application) -> list[dict[str,Any]]:
    return snapshot(app).snapshot_json['forms']


def form(app: Application, form_no: str) -> dict[str,Any]:
    found=next((row for row in forms(app) if row['form_no']==form_no),None)
    if found is None: raise HTTPException(404,'이 신청 건의 서식이 아닙니다.')
    return found


def form_path(row: dict[str,Any]) -> Path:
    root=storage().resolve()
    path=(root/row['path']).resolve()
    if not path.is_relative_to(root) or not path.is_file():
        raise HTTPException(404,'확정된 서식 PDF를 찾을 수 없습니다.')
    return path


def checklist(app: Application) -> list[DocRequirement]:
    requirements=[]
    for raw in snapshot(app).snapshot_json['requirements']:
        value=deepcopy(raw)
        value['doc_type']=DocType(value['doc_type'])
        value['accepted_doc_types']=[DocType(x) for x in value.get('accepted_doc_types',[])]
        for key in ('min_issue_date','max_issue_date'):
            if value.get(key): value[key]=date.fromisoformat(value[key])
        requirements.append(DocRequirement(**value))
    return requirements


def fields(app: Application) -> dict[str,Any]:
    return {key:value for row in forms(app) for key,value in row['fields'].items()}


def values(app: Application, incoming: dict[str,Any], *, phone: str|None=None) -> dict[str,Any]:
    allowed=fields(app)
    clean={}
    for key,raw in incoming.items():
        if key not in allowed: continue
        field=allowed[key]
        kind=field.get('field_type','text')
        if kind in {'check','radio'}:
            if not isinstance(raw,bool): raise HTTPException(422,'선택 입력칸 값을 확인해 주세요.')
            clean[key]=raw
            continue
        if not isinstance(raw,str): raise HTTPException(422,'서식 입력칸에는 글자를 입력해 주세요.')
        if kind=='signature':
            if raw:
                head,sep,payload=raw.partition(',')
                try:
                    data=base64.b64decode(payload,validate=True)
                    if not sep or head!='data:image/png;base64' or not data.startswith(b'\x89PNG\r\n\x1a\n') or len(data)>5*1024*1024:
                        raise ValueError('invalid')
                    with pymupdf.open(stream=data,filetype='png') as image:
                        if not image.page_count: raise ValueError('empty')
                except Exception:
                    raise HTTPException(422,'서명은 정상적인 PNG 이미지(5MB 이하)로 입력해 주세요.') from None
            clean[key]=raw
            continue
        if len(raw)>4000: raise HTTPException(422,'입력칸은 4,000자 이하로 입력해 주세요.')
        raw=mask_data(raw)
        if raw and kind=='date':
            try: date.fromisoformat(raw)
            except ValueError: raise HTTPException(422,'날짜를 YYYY-MM-DD 형식으로 입력해 주세요.') from None
        if raw and kind=='number' and not re.fullmatch(r'[-+]?\d{1,20}(?:\.\d{1,6})?',raw):
            raise HTTPException(422,'숫자 입력칸 값을 확인해 주세요.')
        clean[key]=raw
    groups={}
    for key,field in allowed.items():
        if field.get('field_type')=='radio' and clean.get(key) is True and field.get('group'):
            group=field['group']
            if group in groups:
                raise HTTPException(422,'같은 선택 묶음에서는 하나만 선택해 주세요.')
            groups[group]=key
    identity=app.identity_json or {}
    for key,field in allowed.items():
        source=field.get('autofill_source')
        if identity and source in {'name','birth'}:
            clean[key]=identity.get(source,'')
        elif identity and source in {'mobile','phone'}:
            clean[key]=phone if phone is not None else clean.get(key) or (app.form1_json or {}).get(key) or identity.get('phone','')
    return clean


def application_dict(app: Application) -> dict[str,Any]:
    identity=app.identity_json or {}
    return {'id':app.id,'application_no':app.application_no,'program_code':app.program_code,
        'status':app.status,'form1_json':app.form1_json or {},'self_check_json':{},'form5_json':{},
        'identity_json':{key:identity[key] for key in ('name','birth','phone','method','verified_at') if key in identity} or None,
        'eligibility_blockers':[]}


def officer_form_values(app:Application) -> dict[str,Any]:
    address=next(((app.form1_json or {}).get(key,'') for key,field in fields(app).items() if field.get('autofill_source')=='address'),'')
    return {'name':(app.identity_json or {}).get('name',''),'address':address}


def program_info(app: Application) -> dict[str,Any]:
    raw=snapshot(app).snapshot_json
    return {'code':app.program_code,'name':raw['title'],'title':raw['title'],
        'apply_start':raw['apply_start'],'apply_end':raw['apply_end'],'guidance_text':raw['guidance_text']}


def public_layout(app: Application, form_no: str) -> dict[str,Any]:
    row=form(app,form_no)
    safe={}
    for key,field in row['fields'].items():
        safe[key]={attr:field[attr] for attr in ('type','field_type','page','box','x','y','size','align','font_family','label','required','group','autofill_source') if attr in field}
        safe[key]['readonly']=field.get('autofill_source') in {'name','birth'}
    return {'form_no':form_no,'title':row['title'],'public_form':None,'page_sizes':row['page_sizes'],
        'fields':safe,'requirements':[],'masks':[],'auto_date':date.today().isoformat()}


def form_links(app: Application) -> list[dict[str,Any]]:
    return [{'form_no':row['form_no'],'public_form':None,'title':row['title'],'label':row['title'],
        'file_url':f'/api/applications/{app.id}/forms/{row["form_no"]}.pdf',
        'file_name':f'{app.application_no}_{row["form_no"]}.pdf','hwp_available':False} for row in forms(app)]


def filled_pdf(app: Application, form_no: str) -> tuple[bytes,FormCoords]:
    row=form(app,form_no)
    spec=FormCoords(form_no=form_no,title=row['title'],template=form_path(row),fields=row['fields'],source={})
    filled=FilledForm(form_no=form_no)
    for key,field in row['fields'].items():
        value=(app.form1_json or {}).get(key)
        if field['type']=='check':
            if value is True: filled.checks.append(key)
        elif field['type']=='image':
            if isinstance(value,str) and value.startswith('data:image/png;base64,'):
                filled.images[key]=base64.b64decode(value.partition(',')[2])
        elif value not in (None,''):
            filled.texts[key]=str(value)
    return render(spec,filled),spec


def written_pdf(app: Application) -> tuple[bytes,int]:
    rows=forms(app)
    with pymupdf.open() as output:
        for row in rows:
            payload,_=filled_pdf(app,row['form_no'])
            with pymupdf.open(stream=payload,filetype='pdf') as source: output.insert_pdf(source)
        return output.tobytes(garbage=4,deflate=True),len(rows)


def form_response(app:Application,form_no:str,*,template:bool=False) -> Response:
    payload=form_path(form(app,form_no)).read_bytes() if template else filled_pdf(app,form_no)[0]
    return Response(payload,media_type='application/pdf',headers={'Content-Disposition':'inline','Cache-Control':'no-store'})


def page_response(app:Application,form_no:str,page_no:int,preview:bool,dpi:int) -> Response:
    row=form(app,form_no)
    payload=filled_pdf(app,form_no)[0] if preview else form_path(row).read_bytes()
    try: png=render_page_png(payload,page_no,dpi)
    except IndexError: raise HTTPException(404,'서식 쪽을 찾을 수 없습니다.') from None
    return Response(png,media_type='image/png',headers={'Cache-Control':'no-store'})


def required_missing(app:Application) -> list[dict[str,Any]]:
    missing=[]
    selected_groups={field.get('group') for key,field in fields(app).items() if field.get('field_type')=='radio' and (app.form1_json or {}).get(key) is True and field.get('group')}
    for key,field in fields(app).items():
        if not field.get('required'): continue
        if field.get('field_type')=='radio' and field.get('group') in selected_groups: continue
        value=(app.form1_json or {}).get(key)
        if value is None or value is False or (isinstance(value, str) and not value.strip()):
            missing.append({'kind':'form','target':key,'label':field['label'],'code':'FORM_REQUIRED_MISSING',
                'message':f'{field["label"]} 입력칸을 작성해 주세요.','goto':'forms'})
    return missing


def blockers(app:Application) -> list[dict[str,Any]]:
    from .api.common import list_documents
    from .api.review import document_blockers
    result=[]
    if not app.identity_json:
        result.append({'kind':'identity','target':'identity','label':'본인인증','message':'본인인증을 마쳐 주세요.','goto':'identity'})
    result.extend(required_missing(app))
    result.extend(document_blockers(checklist(app),list_documents(app.id or 0)))
    if app.status=='draft':
        raw=snapshot(app).snapshot_json
        from .api import postings
        current_open=True
        try:
            eligible_posting(app.program_code)
        except HTTPException:
            current_open=False
        frozen_open=date.fromisoformat(raw['apply_start']) <= postings._today() <= date.fromisoformat(raw['apply_end'])
        if not current_open or not frozen_open:
            result.append({'kind':'context','target':'program','label':'신청 접수','code':'PROGRAM_NOT_OPEN',
                'message':'현재 접수 중인 사업이 아닙니다. 사업 안내를 확인해 주세요.','goto':'identity'})
    return result


def final_check(app:Application) -> dict[str,Any]:
    from .api.common import document_dict,list_documents
    info=program_info(app)
    issues=blockers(app)
    return {'application_no':app.application_no,'program_code':app.program_code,'program_name':info['name'],
        'allows_supplement':False,'supplement_days':None,'selection':'manual','first_come':None,'subsidy':None,
        'status':app.status,'can_submit':not issues and app.status=='draft','already_submitted':app.status!='draft',
        'blockers':issues,'warnings':['제출 서류는 담당자가 확인합니다.'],
        'form_summary':[{'label':field['label'],'value':'서명 완료' if field['type']=='image' and (app.form1_json or {}).get(key) else '선택' if (app.form1_json or {}).get(key) is True else str((app.form1_json or {}).get(key) or '')} for key,field in fields(app).items()],
        'documents':[document_dict(row) for row in list_documents(app.id or 0)]}


def run_review(app:Application) -> Review:
    from .api.common import list_documents
    docs=list_documents(app.id or 0)
    by_slot={row.slot_key:row for row in docs}
    all_pass=not required_missing(app) and all(req.slot_key in by_slot and by_slot[req.slot_key].stage1_status=='PASS' for req in checklist(app) if req.required)
    all_pass=all_pass and all(row.stage1_status=='PASS' for row in docs)
    final='PASS' if all_pass else 'NEEDS_REVIEW'
    return Review(application_id=app.id,final_status=final,stage1_status=final,stage2_status=None,
        review_payload_json={'final_status':final,'reasons':[{'code':'PROGRAM_RULES_UNSET','message':NOTICE}]})


def submit(app:Application) -> dict[str,Any]:
    if app.status!='draft': raise HTTPException(400,'이미 제출된 신청입니다.')
    issues=blockers(app)
    if issues: raise HTTPException(400,'아직 제출할 수 없습니다. '+ ' '.join(item['message'] for item in issues))
    review=run_review(app)
    from .api.forms import snapshot_written_pdf
    with get_session() as session:
        row=session.get(Application,app.id)
        row.status='submitted'
        from .forms.values import submission_timestamp
        row.submitted_at=submission_timestamp()
        row.updated_at=row.submitted_at
        row.written_forms_archive_path,row.written_forms_archive_count=snapshot_written_pdf(row)
        session.add(row);session.add(review);session.commit();session.refresh(row)
    return {'application_no':row.application_no,'submitted_at':row.submitted_at.isoformat(timespec='seconds'),
        'status':'submitted','message':'신청이 접수되었습니다.','next_steps':['담당자가 제출 서류와 공고문 기준을 확인합니다.'],
        'first_come':None,'supplement':None,'subsidy':None,'notice':'최종 선정 여부는 담당자 확인 후 안내됩니다.'}


def status(app:Application) -> dict[str,Any]:
    from .api.common import document_dict,list_documents
    info=program_info(app)
    current=-1 if app.status=='draft' else 2 if app.status=='decided' else 1
    labels=['접수','서류검토','결과 안내']
    return {'application_no':app.application_no,'program_code':app.program_code,'program_name':info['name'],'status':app.status,
        'eligibility_blockers':[],'submitted_at':app.submitted_at.isoformat(timespec='seconds') if app.submitted_at else None,
        'progress':[{'label':label,'state':'todo' if current<0 or index>current else 'current' if index==current else 'done'} for index,label in enumerate(labels)],
        'result_notice':'최종 선정 여부는 담당자 확인 후 안내됩니다.','first_come':None,'supplement':None,'subsidy':None,
        'documents':[document_dict(row) for row in list_documents(app.id or 0)],'consents':[],'call_center':''}


def checklist_response(app:Application) -> dict[str,Any]:
    from .api.documents import _requirement_dict
    from .api.common import document_dict,list_documents
    uploaded=list_documents(app.id or 0)
    items=[_requirement_dict(req,uploaded) for req in checklist(app)]
    info=program_info(app)
    return {'context':{},'work_categories':[],'accepted_formats':['pdf','jpg','jpeg','png'],
        'program':{'code':app.program_code,'name':info['name'],'selection':'manual','allows_supplement':False,'supplement_days':None,
            'document_cutoff':'','announcement_date':info['apply_start'],'application_period':[info['apply_start'],info['apply_end']],
            'application_period_2':None,'criteria_version':None,'paper_forms':{},'nhis_payment_months':[],
            'nhis_acquisition_loss_years':None,'asks_work_category':False,'has_subsidy_items':False},
        'items':items,'upload_total':len(items),'upload_done':sum(bool(item['documents']) for item in items),
        'unassigned':[document_dict(row) for row in uploaded if row.slot_key=='unassigned'],'assumption_notes':[]}
