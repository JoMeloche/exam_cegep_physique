import { clsx, type ClassValue } from 'clsx'
import { twMerge } from 'tailwind-merge'

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

const DEFAULT_SESSIONS: Record<string, number[]> = { A: [8, 9, 10, 11, 12], H: [1, 2, 3, 4, 5], E: [6, 7] }

export function sessionCode(d: Date, sessions: Record<string, number[]> = DEFAULT_SESSIONS) {
  const m = d.getMonth() + 1
  const letter = Object.entries(sessions).find(([, months]) => months.includes(m))?.[0] ?? ''
  return `${letter}${String(d.getFullYear() % 100).padStart(2, '0')}`
}

export function fileBaseName(pattern: string | undefined, f: { course: string; exam: number; session: string; version: number; date: Date }) {
  const vals: Record<string, string> = {
    course: f.course, exam: String(f.exam), session: f.session, version: String(f.version),
    date: isoDate(f.date), year: String(f.date.getFullYear()),
  }
  return (pattern || '{course}_Examen_{exam}_{session}_v{version}').replace(/\{(\w+)\}/g, (m, k) => vals[k] ?? m).replace(/[<>:"/\\|?*]+/g, '-')
}

export function isoDate(d: Date) {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}

export function durationText(min: number) {
  const h = Math.floor(min / 60), m = min % 60
  if (h && m) return `${h} h ${String(m).padStart(2, '0')}`
  if (h) return `${h} h`
  return `${m} min`
}

/** Numbers the French way: 2,7 rather than 2.7. */
export function frNumber(x: number, digits = 1) {
  return x.toLocaleString('fr-CA', { minimumFractionDigits: digits, maximumFractionDigits: digits })
}
