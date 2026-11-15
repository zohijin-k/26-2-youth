/**
 * 본인인증 (데모).
 *
 * 업로드 서류가 '이 신청자의 것인지' 대조하려면 기준 신원이 먼저 있어야 한다.
 * 신청서에 손으로 적은 성명·생년월일은 기준이 될 수 없으므로 신청 맨 앞에서 정한다.
 *
 * 실서비스는 로그인할 때 PASS·간편인증으로 받는다. 데모는 그 단계를 흉내 내어
 * 입력값을 그대로 인증 결과로 쓴다. 서약 서명은 신원 증명이 아니라
 * "본인 서류만 제출한다"는 책임 확인이다.
 *
 * 서명은 화면에 직접 하거나, 서명 파일(PNG·JPG·PDF, 5MB 이하)을 올린다.
 */

import { useEffect, useLayoutEffect, useRef, useState, type ReactNode } from 'react'

import { fetchApplication, verifyIdentity, type Identity, type Blocker } from '../../api.ts'
import FilePreview from '../../components/ApplicantFilePreview.tsx'
import PdfPages from '../../components/PdfPages.tsx'
import SignaturePad from '../../components/SignaturePad.tsx'
import ConfirmDialog from '../../components/ConfirmDialog.tsx'
import Icon from '../../components/Icon.tsx'
import MoreInfo from '../../components/MoreInfo.tsx'
import Notice from '../../components/Notice.tsx'
import Spinner from '../../components/Spinner.tsx'
import useBeforeUnload from '../../hooks/useBeforeUnload.ts'
import { friendlyError } from '../../lib/error-copy.ts'
import { formatDate } from '../../lib/format.ts'
import { validateIdentity, IDENTITY_FIELDS, type IdentityField } from '../../lib/identity-validation.ts'
import { formatPhone, phoneCursorPosition } from '../../forms/phone.ts'
import { EMPTY_YMD, ymdToISO, type YMD } from '../../forms/ymd.ts'
import './identity-check.css'

const SIGN_MODES = ['직접 서명', '서명 파일 올리기'] as const
type SignMode = (typeof SIGN_MODES)[number]

const SIGN_FILE_ACCEPT = '.png,.jpg,.jpeg,.pdf'
const SIGN_FILE_MAX = 5 * 1024 * 1024
/** 확장자 → 형식. 브라우저가 형식을 비워 보내는 경우가 있어 확장자로도 판별한다. */
const SIGN_FILE_EXT: Record<string, string> = {
  png: 'image/png',
  jpg: 'image/jpeg',
  jpeg: 'image/jpeg',
  pdf: 'application/pdf',
}

function signFileType(file: File): string | null {
  if (Object.values(SIGN_FILE_EXT).includes(file.type)) return file.type
  const ext = file.name.split('.').pop()?.toLowerCase() ?? ''
  return SIGN_FILE_EXT[ext] ?? null
}

interface SignFile {
  name: string
  type: string
  /** 서버로 보낼 값 */
  dataUrl: string
  /** 화면 미리보기용 (blob URL) */
  previewUrl: string
}

/** 서명 칸의 최대 폭과 높이(px). 폭은 tokens.css의 --sign-max와 같다. */
const SIGN_MAX_WIDTH = 560
const SIGN_HEIGHT = 200

/** 입력 칸 아래에 예시 글이 있는 항목. 나머지는 오류가 있을 때만 설명을 단다. */
const HINTED_FIELDS: IdentityField[] = ['birth', 'phone', 'pledge']

const PLEDGE =
  '본인은 위 정보의 당사자이며, 신청에 제출하는 서류는 모두 본인 명의임을 확인합니다. ' +
  '타인의 서류를 제출하거나 사실과 다른 내용을 제출한 경우 선정 취소 등 불이익을 받는 데 동의합니다.'

interface Props {
  /** 제목 바로 아래에 두는 사업별 안내(일반 사업 신청). */
  lead?: ReactNode
  appId: number | null
  ensureApplication?: () => Promise<number>
  /** 이미 인증을 마쳤으면 결과만 보여준다 */
  identity: Identity | null
  onVerified: (identity: Identity, mobile: string, applicationId: number) => void
  onNext: () => void
}

export default function IdentityCheck({ lead, appId, ensureApplication, identity, onVerified, onNext }: Props) {
  const [name, setName] = useState('')
  const [birth, setBirth] = useState<YMD>(EMPTY_YMD)
  const [phone, setPhone] = useState('')
  const phoneInput = useRef<HTMLInputElement>(null)
  const pendingPhoneCaret = useRef<number | null>(null)
  const [pledge, setPledge] = useState(false)
  const [signMode, setSignMode] = useState<SignMode>('직접 서명')
  const [drawn, setDrawn] = useState('')
  const signBody = useRef<HTMLDivElement>(null)
  const [signWidth, setSignWidth] = useState(320)
  const [file, setFile] = useState<SignFile | null>(null)
  const [fileKey, setFileKey] = useState(0)
  const [viewing, setViewing] = useState(false)
  const fileVersion = useRef(0)
  useEffect(() => () => { fileVersion.current += 1 }, [])
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [touched, setTouched] = useState<Partial<Record<IdentityField, boolean>>>({})
  const [attempted, setAttempted] = useState(false)
  const [confirming, setConfirming] = useState<'identity' | 'clear' | null>(null)
  const signatureValue = signMode === '직접 서명' ? drawn : (file?.dataUrl ?? '')
  const errors = validateIdentity({ name, birth, phone, pledge, signature: signatureValue })
  useBeforeUnload(!identity && (busy || !!name || !!phone || !!signatureValue || Object.values(birth).some(Boolean) || pledge))
  const focusField = (field: IdentityField) => {
    document.querySelector<HTMLElement>(`[data-identity-field="${field}"] input, [data-identity-field="${field}"] button`)?.focus()
  }
  const fieldError = (field: IdentityField) => (attempted || touched[field]) && errors[field]
  const errorLine = (field: IdentityField) => fieldError(field) ? <p className="field__error" id={`identity-${field}-error`}><Icon name="alertCircle" size={18} /><span>{errors[field]}</span></p> : null
  const describedBy = (field: IdentityField) => [
    HINTED_FIELDS.includes(field) && `identity-${field}-hint`,
    fieldError(field) && `identity-${field}-error`,
  ].filter(Boolean).join(' ') || undefined
  const [eligibilityResult, setEligibilityResult] = useState<{
    appId: number; birth: string; blockers: Blocker[]
  } | null>(null)
  const eligibilityBlockers = eligibilityResult?.appId === appId && eligibilityResult.birth === identity?.birth
    ? eligibilityResult.blockers : []

  useEffect(() => {
    if (!identity || appId === null) return
    let active = true
    fetchApplication(appId).then((data) => {
      if (active) setEligibilityResult({ appId, birth: identity.birth, blockers: data.eligibility_blockers ?? [] })
    }).catch(() => {
      if (active) setError('신청 자격 안내를 불러오지 못했습니다. 다시 확인해 주세요.')
    })
    return () => { active = false }
  }, [appId, identity])

  useLayoutEffect(() => {
    const input = phoneInput.current
    const digits = pendingPhoneCaret.current
    if (!input || digits === null) return
    const position = phoneCursorPosition(phone, digits)
    input.setSelectionRange(position, position)
    pendingPhoneCaret.current = null
  }, [phone])

  // 미리보기 URL은 파일을 바꾸거나 화면을 떠날 때 해제한다.
  useEffect(() => {
    if (!file) return undefined
    return () => URL.revokeObjectURL(file.previewUrl)
  }, [file])

  useLayoutEffect(() => {
    const body = signBody.current
    if (!body) return undefined
    const updateWidth = () => setSignWidth(Math.min(SIGN_MAX_WIDTH, Math.max(1, Math.floor(body.clientWidth))))
    updateWidth()
    const observer = new ResizeObserver(updateWidth)
    observer.observe(body)
    return () => observer.disconnect()
  }, [identity])

  if (identity) {
    return (
      <section className="idcheck">
        <h2 className="idcheck__title">본인인증</h2>
        {lead}
        {eligibilityBlockers.map((blocker) => (
          <Notice key={blocker.target} tone="danger" role="alert">{blocker.message}</Notice>
        ))}
        {error && <Notice tone="danger" role="alert">{error}</Notice>}
        <Notice tone="success" title="본인인증을 마쳤습니다.">
          <dl className="fact-list idcheck__verified">
            <div>
              <dt>성명</dt>
              <dd>{identity.name}</dd>
            </div>
            <div>
              <dt>생년월일</dt>
              <dd>{formatDate(identity.birth)}</dd>
            </div>
            <div>
              <dt>휴대폰</dt>
              <dd>{identity.phone}</dd>
            </div>
          </dl>
        </Notice>
        <p className="idcheck__after">
          신청서의 성명·생년월일은 이 정보로 채워지며 고칠 수 없습니다. 올리시는 서류도 이
          정보와 같은 사람의 것인지 확인합니다.
        </p>
        <div className="flow__actions">
          <button type="button" className="btn btn--primary btn--lg" onClick={onNext}>
            서식 작성하기
          </button>
        </div>
      </section>
    )
  }

  const birthISO = ymdToISO(birth)
  const signature = signMode === '직접 서명' ? drawn : (file?.dataUrl ?? '')

  /** 서명 파일을 data URL로 읽는다. 형식·크기는 서버도 다시 확인한다. */
  const pickFile = (picked: File | undefined) => {
    const version = ++fileVersion.current
    setError('')
    if (!picked) {
      setFile(null)
      return
    }
    const type = signFileType(picked)
    if (!type) {
      setFile(null)
      setError('서명 파일은 PNG·JPG·PDF만 올릴 수 있습니다.')
      return
    }
    if (!picked.size) { setError('파일 내용이 비어 있습니다. 서명 파일을 다시 선택해 주세요.'); return }
    if (picked.size > SIGN_FILE_MAX) {
      setFile(null)
      setError('서명 파일은 5MB 이하로 올려 주세요.')
      return
    }
    const reader = new FileReader()
    reader.onerror = () => { if (version === fileVersion.current) setError('서명 파일을 읽지 못했습니다. 다시 선택해 주세요.') }
    reader.onload = () => {
      if (version !== fileVersion.current) return
      // 형식을 비워 보낸 파일도 서버가 읽을 수 있게 data URL 머리를 판별한 형식으로 맞춘다.
      const raw = String(reader.result)
      const dataUrl = `data:${type};base64,${raw.slice(raw.indexOf(',') + 1)}`
      setFile({ name: picked.name, type, dataUrl, previewUrl: URL.createObjectURL(picked) })
    }
    reader.readAsDataURL(picked)
  }

  const clearFile = () => {
    fileVersion.current += 1
    setFile(null)
    setFileKey((k) => k + 1) // 같은 파일을 다시 고를 수 있게 입력칸을 새로 만든다
  }

  const submit = async () => {
    setConfirming(null)
    setBusy(true)
    setError('')
    try {
      const applicationId = appId ?? await ensureApplication?.()
      if (applicationId === undefined) throw new Error('신청 정보를 준비하지 못했습니다. 다시 시도해 주세요.')
      const result = await verifyIdentity(applicationId, {
        name,
        birth: birthISO,
        phone,
        pledge,
        signature_data_url: signature,
        signature_kind: signMode === '직접 서명' ? 'electronic' : 'uploaded',
      })
      onVerified(result, phone, applicationId)
    } catch (e) {
      setError(friendlyError(e, '본인인증을 완료하지 못했습니다. 다시 시도해 주세요.'))
    } finally {
      setBusy(false)
    }
  }

  return (
    <section className="idcheck" onBlurCapture={(event) => {
      const field = (event.target as HTMLElement).closest<HTMLElement>('[data-identity-field]')?.dataset.identityField as IdentityField | undefined
      if (field && !event.currentTarget.querySelector(`[data-identity-field="${field}"]`)?.contains(event.relatedTarget as Node)) setTouched((current) => ({ ...current, [field]: true }))
    }}>
      <h2 className="idcheck__title">본인인증</h2>
        {lead}
      <Notice tone="info" title="본인 명의의 서류와 서명을 준비해 주세요">
        <MoreInfo summary="신청 전 확인 사항 보기">
          <ul>
            <li>신청은 본인인증 → 서식 작성 → 서류 업로드 → 확인 및 제출 순서로 진행합니다.</li>
            <li>증빙서류는 발급처에서 받은 PDF 파일을 권장합니다.</li>
            <li>작성 중인 신청은 이 창(탭)에서만 이어서 쓸 수 있습니다. 제출을 마칠 때까지 창을 닫지 마세요.</li>
            <li>본인인증에 입력한 성명·생년월일은 신청서에 그대로 들어가며 나중에 고칠 수 없습니다.</li>
            <li>데모 화면입니다. 실제 서비스에서는 로그인할 때 휴대폰·간편인증으로 대신합니다.</li>
          </ul>
        </MoreInfo>
      </Notice>
      {attempted && Object.keys(errors).length > 0 && <Notice tone="danger" role="alert" title={`입력 내용을 ${Object.keys(errors).length}곳 확인해 주세요.`}>
        <ul>{IDENTITY_FIELDS.filter((field) => errors[field]).map((field) => <li key={field}><a href={`#identity-${field}`} onClick={(event) => { event.preventDefault(); focusField(field) }}>{errors[field]}</a></li>)}</ul>
      </Notice>}

      <div className="idcheck__form card">
        <div className="field idcheck__field" data-identity-field="name" id="identity-name">
          <label htmlFor="identity-name-input" className="field__label">성명<span className="field__req">필수</span></label>
          <input
            className="input"
            value={name}
            onChange={(e) => setName(e.target.value)}
            id="identity-name-input"
            aria-required="true"
            aria-invalid={!!fieldError('name')}
            aria-describedby={describedBy('name')}
            autoComplete="name"
          />
          {errorLine('name')}
        </div>
        <fieldset className="field" data-identity-field="birth" id="identity-birth">
          <legend className="field__label">생년월일<span className="field__req">필수</span></legend>
          <div className="date-triple--ui">
            {(['y', 'm', 'd'] as const).map((part, index) => <span key={part} className="idcheck__date-part"><input className={`input date-triple__${part}`} inputMode="numeric" aria-label={`생년월일 ${['연도', '월', '일'][index]}`} aria-required="true" aria-invalid={!!fieldError('birth')} aria-describedby={describedBy('birth')} value={birth[part]} onChange={(event) => setBirth({ ...birth, [part]: event.target.value })} /><span className="date-triple__unit">{['년', '월', '일'][index]}</span></span>)}
          </div>
          <p className="field__hint" id="identity-birth-hint">예: 1998년 6월 15일</p>{errorLine('birth')}
        </fieldset>
        <div className="field idcheck__field" data-identity-field="phone" id="identity-phone">
          <label htmlFor="identity-phone-input" className="field__label">휴대폰<span className="field__req">필수</span></label>
          <input
            className="input"
            type="tel"
            inputMode="numeric"
            autoComplete="tel"
            maxLength={13}
            placeholder="010-0000-0000"
            value={phone}
            ref={phoneInput}
            onChange={(e) => {
              const input = e.currentTarget
              const beforeCursor = input.value.slice(0, input.selectionStart ?? input.value.length)
              let digitCount = beforeCursor.replace(/\D/g, '').length
              if (beforeCursor.trimStart().startsWith('+82') && digitCount >= 2) digitCount -= 1
              pendingPhoneCaret.current = digitCount
              setPhone(formatPhone(input.value))
            }}
            onPaste={(e) => {
              const pasted = e.clipboardData.getData('text')
              if (!pasted) return
              e.preventDefault()
              const formatted = formatPhone(pasted)
              pendingPhoneCaret.current = formatted.replace(/\D/g, '').length
              setPhone(formatted)
            }}
            onKeyDown={(e) => {
              const input = e.currentTarget
              const cursor = input.selectionStart
              if (
                e.key !== 'Backspace' ||
                cursor === null ||
                cursor !== input.selectionEnd ||
                cursor === 0 ||
                input.value[cursor - 1] !== '-'
              ) return
              e.preventDefault()
              const digitCount = input.value.slice(0, cursor).replace(/\D/g, '').length
              const digits = phone.replace(/\D/g, '')
              if (digitCount === 0) return
              pendingPhoneCaret.current = digitCount - 1
              setPhone(formatPhone(`${digits.slice(0, digitCount - 1)}${digits.slice(digitCount)}`))
            }}
            id="identity-phone-input"
            aria-required="true"
            aria-invalid={!!fieldError('phone')}
            aria-describedby={describedBy('phone')}
          />
          <p className="field__hint" id="identity-phone-hint">010으로 시작하는 번호</p>{errorLine('phone')}
        </div>

        <div className="card__panel idcheck__pledge" data-identity-field="pledge" id="identity-pledge">
          <h3 className="idcheck__pledge-title">본인 확인 서약<span className="field__req">필수</span></h3>
          <p className="idcheck__pledge-text" id="identity-pledge-hint">{PLEDGE}</p>
          <label className="check idcheck__agree">
            <input type="checkbox" aria-required="true" aria-invalid={!!fieldError('pledge')} aria-describedby={describedBy('pledge')} checked={pledge} onChange={(e) => setPledge(e.target.checked)} />
            <span>위 내용을 확인했으며 동의합니다.</span>
          </label>
          {errorLine('pledge')}
        </div>

        <div className="field idcheck__sign" data-identity-field="signature" id="identity-signature">
          <span className="field__label" id="identity-sign-label">서명<span className="field__req">필수</span></span>
          {/* 둘 중 하나를 고르는 두 칸짜리 전환 단추. 실제로는 라디오 두 개다. */}
          <div className="segmented idcheck__modes" role="radiogroup" aria-labelledby="identity-sign-label" aria-describedby={describedBy('signature')}>
            {SIGN_MODES.map((m) => (
              <label key={m} className="segmented__option">
                <input
                  type="radio"
                  name="identity-sign-mode"
                  checked={signMode === m}
                  onChange={() => {
                    setSignMode(m)
                    setError('')
                  }}
                />
                <span>
                  {signMode === m && <Icon name="check" size={18} />}
                  {m}
                </span>
              </label>
            ))}
          </div>
          <div className={fieldError('signature') ? 'idcheck__sign-area is-invalid' : 'idcheck__sign-area'} ref={signBody}>
            {signMode === '직접 서명' ? (
              <SignaturePad key={drawn ? `signed-${signWidth}` : `empty-${signWidth}`} value={drawn} onChange={setDrawn} width={signWidth} height={SIGN_HEIGHT} />
            ) : (
              <div className="idcheck__file">
                {file ? (
                  <button type="button" className="idcheck__preview" onClick={() => setViewing(true)} aria-label="올린 서명 크게 보기">
                    {file.type === 'application/pdf' ? (
                      <PdfPages url={file.previewUrl} width={Math.max(1, Math.min(signWidth - 48, 280))} maxHeight={112} maxPages={1} />
                    ) : (
                      <img src={file.previewUrl} alt="올린 서명 미리보기" />
                    )}
                    <span className="idcheck__zoomhint" aria-hidden="true"><Icon name="eye" size={16} />크게 보기</span>
                  </button>
                ) : (
                  <p className="idcheck__file-guide">
                    <Icon name="upload" size={24} />
                    <span>PNG·JPG·PDF 서명 파일을 올려 주세요. (5MB 이하)</span>
                  </p>
                )}
                {file && <p className="idcheck__filename">{file.name}</p>}
                <input
                  key={fileKey}
                  id="identity-sign-file"
                  className="sr-only"
                  type="file"
                  accept={SIGN_FILE_ACCEPT}
                  aria-label="서명 파일"
                  onChange={(e) => pickFile(e.target.files?.[0])}
                />
                <label className="btn idcheck__file-pick" htmlFor="identity-sign-file"><Icon name="upload" />{file ? '다른 파일 선택' : '파일 선택'}</label>
              </div>
            )}
          </div>
          {file && viewing && (
            <FilePreview
              url={file.previewUrl}
              name={file.name}
              kind={file.type === 'application/pdf' ? 'pdf' : 'image'}
              onClose={() => setViewing(false)}
            />
          )}
          <div className="idcheck__sign-foot">
            {errorLine('signature') ?? <span />}
            <button type="button" className="btn btn--quiet btn--small" disabled={!signatureValue} onClick={() => setConfirming('clear')}>
              <Icon name="trash" size={18} />
              지우기
            </button>
          </div>
        </div>
      </div>

      {error && <Notice tone="danger" role="alert">{error}</Notice>}

      <div className="flow__actions">
        <button
          type="button"
          className="btn btn--primary btn--lg"
          disabled={busy}
          onClick={() => {
            setAttempted(true)
            const first = IDENTITY_FIELDS.find((field) => errors[field])
            if (first) focusField(first)
            else setConfirming('identity')
          }}
        >
          {busy && <Spinner />}{busy ? '본인인증 하는 중' : '본인인증 하기'}
        </button>
      </div>
      {confirming === 'identity' && <ConfirmDialog title="입력하신 정보로 본인인증 하시겠습니까?" description="본인인증 후에는 성명과 생년월일을 수정할 수 없습니다." confirmLabel="본인인증 하기" onCancel={() => setConfirming(null)} onConfirm={() => void submit()}>
        <dl className="fact-list"><div><dt>성명</dt><dd>{name}</dd></div><div><dt>생년월일</dt><dd>{formatDate(birthISO)}</dd></div><div><dt>휴대폰</dt><dd>{phone}</dd></div></dl>
      </ConfirmDialog>}
      {confirming === 'clear' && <ConfirmDialog title="작성하신 서명을 지우시겠습니까?" description="서명을 지우면 다시 그리거나 서명 파일을 선택해야 합니다." confirmLabel="서명 지우기" tone="danger" onCancel={() => setConfirming(null)} onConfirm={() => { if (signMode === '직접 서명') setDrawn(''); else clearFile(); setConfirming(null) }} />}
    </section>
  )
}
