export type QType = 'developpement' | 'conceptuel'

export interface Topic { name: string; label: string; n_dev: number; n_concept: number }
export interface Course { code: string; title?: string; full_title?: string; group?: string; topics: Topic[]; exams: number[] }
export interface CourseInfo { title?: string; full_title?: string; group?: string; questions_from?: string[] }
export interface Config {
  setup_done: boolean
  school: string
  logo: string
  professors: string[]
  default_professor: string
  courses: Record<string, CourseInfo>
  topics: Record<string, string>
  latex: { engine: string; path: string }
  time_margin: number
  default_versions: number
  naming: { file_pattern: string; solution_suffix: string; exam_label: string; version_label: string }
  sessions: Record<string, number[]>
  cover: { instructions: string; note: string; professor_label: string; name_label: string }
}
export interface QuestionSummary {
  id: string; course: string; topic: string; name: string; title: string; type: QType; points: number
  time_min: number; difficulty: number; solution_mode: string; n_variables: number; tags: string[]
  last_used: string; times_used: number; needs_review: boolean; excerpt?: string; answer?: string
  shared_by?: string; read_only?: boolean; my_share?: 'all' | 'users' | null
}
export interface VariableSpec {
  type: 'integer' | 'decimal' | 'sigfig' | 'choice' | 'text'
  min?: number; max?: number; step?: number; decimals?: number; sigfigs?: number; values?: (string | number)[]
  unit?: string; label?: string; si?: number; si_unit?: string; symbol?: string
}
export interface PartSpec { find?: string; equation?: string; expr?: string; unit?: string; label?: string; symbol?: string; root?: string }
export interface QuestionMeta {
  title: string; type: QType; points: number; time_min: number; difficulty: number; figures: string[]; tags?: string[]
  variables?: Record<string, VariableSpec>; constraints?: string[]
  solution: { mode: 'manual' | 'auto' | 'answers_only' | 'none'; file?: string; parts?: Record<string, PartSpec> }
  answer?: string; explanation?: string; choices?: string[]; [k: string]: unknown
}
export interface QuestionFull extends QuestionSummary {
  meta: QuestionMeta; body: string; solution_tex: string; problems: string[]; usage: { date: string; exam: string }[]
}
export interface ExamSlot { topic?: string; topics?: string[]; count: number; points?: number | null }
export interface ExamSection { title: string; type: QType; points?: number | null; slots: ExamSlot[] }
export interface ExamDef { course: string; number: number; duration_min: number; sections: ExamSection[]; saved?: boolean }
export interface Placed {
  slot: string; section: number; question_id: string; points: number; values: Record<string, unknown>
  answer: string; title?: string; time_min?: number; difficulty?: number; type?: QType; topic?: string; shared_by?: string
}
export interface Plan {
  seed: number; warnings: string[]; session: string; export_dir: string; exam_def: ExamDef
  versions: { number: number; basename: string; placed: Placed[] }[]
}
export interface ExamRequest {
  course: string; exam_number: number; date: string; professor: string; duration_min: number; n_versions: number
  mode: 'same' | 'different'; seed?: number; locks?: Record<string, string>; exam_def?: ExamDef
  shuffle_conceptual?: boolean; shuffle_choices?: boolean; include_shared?: boolean
}
export interface ExportResult { folder: string; files: { name: string; url: string; path: string }[]; warnings: string[]; seed: number }
export interface TestResult { problems: string[]; pdf: string | null; draws: Record<string, string>[]; answers: { key: string; name: string; value: string; unit: string }[][]; log?: string }

export class ApiError extends Error {
  constructor(message: string, public status: number, public data: unknown) { super(message) }
}

export interface AuthUser { id: number; email: string; name: string; role: 'admin' | 'user'; status: string }
export interface AuthState {
  enabled: boolean; user: AuthUser | null; needs_setup?: boolean; pending?: number
  library_mode: 'per-user' | 'shared' | 'local'; sharing: boolean
}
export type UserStatus = 'pending' | 'approved' | 'rejected' | 'disabled'
export interface AdminUser extends AuthUser {
  status: UserStatus; reason: string; note: string; created_at: string; decided_at: string | null
  decided_by: string | null; last_login: string | null
}
export interface Person { id: number; name: string; email: string }
export interface Share { id: number; target: string; audience: 'all' | 'users'; created_at: string; users: Person[] }

/** CSRF: the server checks that writes echo the token it put in this (non-HttpOnly) cookie. */
export function csrfToken(): string {
  const m = document.cookie.match(/(?:^|;\s*)examgen_csrf=([^;]+)/)
  return m ? decodeURIComponent(m[1]) : ''
}

function headersFor(method: string, json: boolean): Record<string, string> {
  const h: Record<string, string> = {}
  if (json) h['Content-Type'] = 'application/json'
  if (!['GET', 'HEAD'].includes(method)) h['X-CSRF-Token'] = csrfToken()
  return h
}

async function req<T>(method: string, url: string, body?: unknown): Promise<T> {
  const r = await fetch(url, {
    method,
    credentials: 'same-origin',
    headers: headersFor(method, body !== undefined),
    body: body !== undefined ? JSON.stringify(body) : undefined,
  })
  const text = await r.text()
  let data = null
  try { data = text ? JSON.parse(text) : null } catch { data = null }
  if (r.status === 401 && !url.startsWith('/api/auth/')) window.dispatchEvent(new Event('examgen:signed-out'))
  if (!r.ok) {
    let msg = `Erreur ${r.status}`
    const d = data?.detail
    if (typeof d === 'string') msg = d
    else if (d?.detail) msg = d.detail + (d.problems ? ' : ' + d.problems.join(' · ') : '')
    throw new ApiError(msg, r.status, data)
  }
  return data as T
}

const enc = (id: string) => id.split('/').map(encodeURIComponent).join('/')

export const api = {
  health: () => req<{ version: string; root: string; desktop: boolean; latex: string | null; platform: string; auth?: boolean; latex_locked?: boolean }>('GET', '/api/health'),
  config: () => req<Config>('GET', '/api/config'),
  saveConfig: (c: Partial<Config>) => req<Config>('PUT', '/api/config', c),
  courses: () => req<Course[]>('GET', '/api/courses'),
  questions: (p: { course?: string; topic?: string; type?: string; q?: string; scope?: 'mine' | 'shared' | 'all' } = {}) => {
    const s = new URLSearchParams(Object.entries(p).filter(([, v]) => v) as [string, string][])
    return req<{ items: QuestionSummary[]; errors: Record<string, string> }>('GET', `/api/questions?${s}`)
  },
  question: (id: string) => req<QuestionFull>('GET', `/api/questions/${enc(id)}`),
  saveQuestion: (p: unknown) => req<QuestionFull>('PUT', '/api/questions', p),
  deleteQuestion: (id: string) => req<{ deleted: string }>('DELETE', `/api/questions/${enc(id)}`),
  testQuestion: (p: unknown) => req<TestResult>('POST', '/api/questions/test', p),
  examDef: (course: string, n: number) => req<ExamDef>('GET', `/api/exams/${encodeURIComponent(course)}/${n}`),
  saveExamDef: (e: ExamDef) => req<ExamDef>('PUT', `/api/exams/${encodeURIComponent(e.course)}/${e.number}`, e),
  plan: (r: ExamRequest) => req<Plan>('POST', '/api/exams/plan', r),
  alternatives: (r: ExamRequest & { slot: string; exclude: string[] }) => req<QuestionSummary[]>('POST', '/api/exams/alternatives', r),
  exportExam: (r: ExamRequest) => req<ExportResult>('POST', '/api/exams/export', r),
  exports: () => req<{ course: string; name: string; files: string[]; folder: string; modified: string }[]>('GET', '/api/exports'),
  open: (path: string, reveal = false) => req<{ ok: boolean }>('POST', '/api/open', { path, reveal }),
  figures: () => req<string[]>('GET', '/api/figures'),
  uploadFigure: async (file: File) => {
    const fd = new FormData(); fd.append('file', file)
    const r = await fetch('/api/figures', { method: 'POST', body: fd, headers: headersFor('POST', false) })
    if (!r.ok) throw new ApiError((await r.json()).detail ?? 'Erreur', r.status, null)
    return (await r.json()) as { name: string }
  },
}

export const authApi = {
  state: () => req<AuthState>('GET', '/api/auth/state'),
  login: (email: string, password: string) => req<{ user: AuthUser }>('POST', '/api/auth/login', { email, password }),
  logout: () => req<{ ok: boolean }>('POST', '/api/auth/logout', {}),
  signup: (p: { name: string; email: string; password: string; reason: string; website?: string }) =>
    req<{ ok: boolean; message: string }>('POST', '/api/auth/signup', p),
  setup: (p: { token: string; name: string; email: string; password: string }) => req<{ user: AuthUser }>('POST', '/api/auth/setup', p),
  changePassword: (current_password: string, new_password: string) =>
    req<{ ok: boolean }>('POST', '/api/auth/password', { current_password, new_password }),
  users: (status?: UserStatus) => req<{ users: AdminUser[]; counts: Record<UserStatus, number> }>('GET', `/api/admin/users${status ? `?status=${status}` : ''}`),
  act: (id: number, action: 'approve' | 'reject' | 'disable' | 'enable' | 'make-admin' | 'make-user' | 'reset-password', note?: string) =>
    req<{ user: AdminUser; temporary_password?: string }>('POST', `/api/admin/users/${id}/${action}`, note ? { note } : {}),
  remove: (id: number) => req<{ deleted: number }>('DELETE', `/api/admin/users/${id}`),
}

export const shareApi = {
  list: () => req<{ shares: Share[]; users: Person[] }>('GET', '/api/shares'),
  set: (target: string, audience: 'all' | 'users', user_ids: number[]) => req<Share>('PUT', '/api/shares', { target, audience, user_ids }),
  remove: (id: number) => req<{ deleted: number }>('DELETE', `/api/shares/${id}`),
  copy: (id: string) => req<{ id: string }>('POST', '/api/shares/copy', { id }),
}
