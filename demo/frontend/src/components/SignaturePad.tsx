/**
 * 캔버스 전자서명.
 *
 * 신청서와 동의서의 서명 입력을 전자서명으로
 * 대체해 "수기 0건"을 보여주되, 현행 지침과 다르다는 점을 화면에 드러낸다.
 * 전자서명 대체 가능 여부는 TF 확인사항이다.
 */

import { useEffect, useRef, useState } from 'react'
import ConfirmDialog from './ConfirmDialog.tsx'

interface Props {
  /** data:image/png;base64,... 또는 빈 문자열 */
  value: string
  onChange: (dataUrl: string) => void
  width?: number
  height?: number
  allowImage?: boolean
}

export default function SignaturePad({ value, onChange, width = 260, height = 90, allowImage = false }: Props) {
  const ref = useRef<HTMLCanvasElement>(null)
  const drawing = useRef(false)
  const lastDrawn = useRef('')
  const canvasSize = useRef('')
  const imageRequest = useRef(0)
  useEffect(() => () => { imageRequest.current += 1 }, [])
  const [clearing, setClearing] = useState(false)
  const [fileError, setFileError] = useState('')
  const [empty, setEmpty] = useState(!value)
  // 고해상도 화면에서 획이 흐려지지 않게 캔버스를 화면 배율만큼 크게 잡는다.
  const [dpr] = useState(() => Math.max(1, Math.round(window.devicePixelRatio || 1)))

  // 저장된 서명이 있으면 되살린다 (임시저장 후 복귀 등).
  useEffect(() => {
    const size = `${width}:${height}:${dpr}`
    const sameSize = canvasSize.current === size
    canvasSize.current = size
    if (sameSize && value && value === lastDrawn.current) return
    const canvas = ref.current
    if (!canvas) return
    const ctx = canvas.getContext('2d')
    if (!ctx) return
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
    ctx.clearRect(0, 0, width, height)
    if (!value) return
    const img = new Image()
    let active = true
    img.onload = () => { if (active) { ctx.drawImage(img, 0, 0, width, height); setEmpty(false) } }
    img.src = value
    return () => { active = false }
  }, [value, width, height, dpr])

  const pos = (e: React.PointerEvent<HTMLCanvasElement>) => {
    const r = e.currentTarget.getBoundingClientRect()
    return { x: (e.clientX - r.left) * width / r.width, y: (e.clientY - r.top) * height / r.height }
  }

  const start = (e: React.PointerEvent<HTMLCanvasElement>) => {
    const ctx = ref.current?.getContext('2d')
    if (!ctx) return
    imageRequest.current += 1
    e.currentTarget.setPointerCapture(e.pointerId)
    drawing.current = true
    const { x, y } = pos(e)
    ctx.lineWidth = 2.2
    ctx.lineCap = 'round'
    ctx.lineJoin = 'round'
    ctx.strokeStyle = '#111'
    ctx.beginPath()
    ctx.moveTo(x, y)
  }

  const move = (e: React.PointerEvent<HTMLCanvasElement>) => {
    if (!drawing.current) return
    const ctx = ref.current?.getContext('2d')
    if (!ctx) return
    const { x, y } = pos(e)
    ctx.lineTo(x, y)
    ctx.stroke()
    setEmpty(false)
  }

  const end = () => {
    if (!drawing.current) return
    drawing.current = false
    const canvas = ref.current
    if (canvas) { lastDrawn.current = canvas.toDataURL('image/png'); onChange(lastDrawn.current) }
  }

  const clear = () => {
    const canvas = ref.current
    const ctx = canvas?.getContext('2d')
    if (!canvas || !ctx) return
    imageRequest.current += 1
    ctx.clearRect(0, 0, width, height)
    setClearing(false)
    lastDrawn.current = ''
    setEmpty(true)
    onChange('')
  }

  return (
    <span className="signature-box">
      <span className="signature-frame" style={{ width, height }}>
        <canvas
          ref={ref}
          className="signature-pad"
          width={width * dpr}
          height={height * dpr}
          style={{ width, height }}
          onPointerDown={start}
          onPointerMove={move}
          onPointerUp={end}
          onPointerLeave={end}
          aria-label="전자서명 입력란"
        />
        {empty && (
          <span className="signature-placeholder" aria-hidden="true">
            여기에 서명해 주세요
          </span>
        )}
      </span>
      <span className="signature-actions">
        <button type="button" className="btn btn--quiet btn--small signature-clear" onClick={() => setClearing(true)} disabled={empty}>
          지우기
        </button>
        <span className={empty ? 'signature-state' : 'signature-state signature-state--done'}>
          {empty ? '서명 전' : '서명 완료'}
        </span>
      </span>
      {allowImage && <label className="signature-image">서명 이미지 선택 (PNG, 5MB 이하)<input type="file" accept=".png" onChange={(event) => {
        const file = event.target.files?.[0]
        event.target.value = ''
        if (!file) return
        const request = ++imageRequest.current
        if (!file.name.toLowerCase().endsWith('.png') || !file.size || file.size > 5 * 1024 * 1024) { setFileError('내용이 있는 PNG 서명 이미지(5MB 이하)를 선택해 주세요.'); return }
        setFileError('')
        const reader = new FileReader()
        const fail = () => {
          if (request === imageRequest.current) setFileError('이미지를 읽지 못했습니다. 정상적인 PNG 파일을 다시 선택해 주세요.')
        }
        reader.onerror = fail
        reader.onload = () => {
          if (request !== imageRequest.current) return
          const image = new Image()
          image.onerror = fail
          image.onload = () => {
            if (request !== imageRequest.current) return
            const prepared = document.createElement('canvas')
            prepared.width = width
            prepared.height = height
            const context = prepared.getContext('2d')
            if (!context || !image.naturalWidth || !image.naturalHeight) { fail(); return }
            const scale = Math.min(width / image.naturalWidth, height / image.naturalHeight)
            const fittedWidth = image.naturalWidth * scale
            const fittedHeight = image.naturalHeight * scale
            context.drawImage(image, (width - fittedWidth) / 2, (height - fittedHeight) / 2, fittedWidth, fittedHeight)
            lastDrawn.current = ''
            onChange(prepared.toDataURL('image/png'))
          }
          image.src = String(reader.result)
        }
        reader.readAsDataURL(file)
      }} /></label>}
      {fileError && <span className="field__error" role="alert">{fileError}</span>}
      {clearing && <ConfirmDialog title="작성하신 서명을 지우시겠습니까?" confirmLabel="서명 지우기" tone="danger" onCancel={() => setClearing(false)} onConfirm={clear} />}
    </span>
  )
}
