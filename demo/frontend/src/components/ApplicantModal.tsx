import type { ReactNode } from 'react'
import Dialog from './Dialog.tsx'
export default function ApplicantModal({title, onClose, children, footer, variant = 'default'}: {
  title: string; onClose: () => void; children: ReactNode; footer?: ReactNode; variant?: 'default' | 'viewer' | 'printable-viewer'
}) {
  return <Dialog title={title} onClose={onClose} footer={footer} size="lg" className={variant === 'default' ? '' : `document-dialog${variant === 'printable-viewer' ? ' document-dialog--printable' : ''}`}>{children}</Dialog>
}
