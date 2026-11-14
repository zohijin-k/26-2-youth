/** Visiting identity never allocates an application; submission reuses the saved draft. */
export const ACTIVE_APPLICATION_KEY = 'applicant.activeApplicationId'

type SessionApplication = { id: number; program_code: string }
type SessionStorage = Pick<Storage, 'getItem' | 'setItem' | 'removeItem'>

export function createIdentitySession<T extends SessionApplication>(options: {
  programCode: string
  storage: () => SessionStorage
  load: (id: number) => Promise<T>
  create: (programCode: string) => Promise<T>
}) {
  let remembered: T | null = null
  let pending: Promise<T> | null = null
  const forget = () => {
    remembered = null
    try { options.storage().removeItem(ACTIVE_APPLICATION_KEY) } catch { /* In-memory submission still works. */ }
  }
  const restore = async (): Promise<T | null> => {
    let id = remembered?.id
    try {
      const saved = options.storage().getItem(ACTIVE_APPLICATION_KEY)
      if (saved && /^[1-9]\d*$/.test(saved) && Number.isSafeInteger(Number(saved))) id = Number(saved)
    } catch { /* Use the current in-memory application if storage is disabled. */ }
    if (id === undefined) return null
    try {
      const application = await options.load(id)
      if (application.program_code !== options.programCode) { forget(); return null }
      remembered = application
      return application
    } catch (error: unknown) {
      if (!(error instanceof Error) || !/실패 \(404\)/.test(error.message)) throw error
      forget()
      return null
    }
  }
  const ensure = (): Promise<T> => {
    if (!pending) {
      pending = restore().then(async (saved) => {
        const application = saved ?? await options.create(options.programCode)
        remembered = application
        try { options.storage().setItem(ACTIVE_APPLICATION_KEY, String(application.id)) } catch { /* Retry uses the remembered application. */ }
        return application
      }).catch((error: unknown) => { pending = null; throw error })
    }
    return pending
  }
  return { restore, ensure }
}
