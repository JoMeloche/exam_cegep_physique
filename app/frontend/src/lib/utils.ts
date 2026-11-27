import { clsx, type ClassValue } from 'clsx'
import { twMerge } from 'tailwind-merge'

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

export function sessionCode(d: Date) {
  const m = d.getMonth() + 1
  const letter = m >= 8 ? 'A' : m <= 5 ? 'H' : 'E'
  return `${letter}${String(d.getFullYear() % 100).padStart(2, '0')}`
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
