import type { ReactNode } from 'react'

/** Обёртка секции: одинаковый вертикальный ритм и разделительная линия. */
export function Section({
  id,
  eyebrow,
  title,
  lede,
  children,
  bordered = true,
}: {
  id?: string
  eyebrow?: string
  title?: string
  lede?: string
  children?: ReactNode
  bordered?: boolean
}) {
  return (
    <section
      id={id}
      className={`px-5 sm:px-8 ${bordered ? 'border-t border-line' : ''}`}
    >
      <div className="mx-auto max-w-5xl py-14 sm:py-20 lg:py-28">
        {(eyebrow || title || lede) && (
          <header className="max-w-2xl">
            {eyebrow && <Eyebrow>{eyebrow}</Eyebrow>}
            {title && (
              <h2 className="mt-3 text-[length:var(--text-step-2)] sm:text-[length:var(--text-step-3)]">
                {title}
              </h2>
            )}
            {lede && (
              <p className="mt-4 text-ink-2 text-[length:var(--text-step-1)] leading-relaxed">
                {lede}
              </p>
            )}
          </header>
        )}
        {children}
      </div>
    </section>
  )
}

export function Eyebrow({ children }: { children: ReactNode }) {
  return (
    <p className="text-[length:var(--text-step--1)] uppercase tracking-[0.14em] text-ink-3">
      {children}
    </p>
  )
}

/** Ссылка-кнопка. Высота 48px перекрывает минимум для касания. */
export function ButtonLink({
  href,
  children,
  variant = 'primary',
}: {
  href: string
  children: ReactNode
  variant?: 'primary' | 'quiet'
}) {
  const base =
    'inline-flex items-center justify-center gap-2 px-6 min-h-12 text-[length:var(--text-step-0)] font-semibold transition-colors duration-200'
  const styles =
    variant === 'primary'
      ? 'bg-navy text-paper hover:bg-ink'
      : 'text-navy underline underline-offset-4 decoration-line hover:decoration-navy'

  return (
    <a href={href} className={`${base} ${styles}`}>
      {children}
    </a>
  )
}

const levelStyles = {
  ok: { dot: 'bg-ok', chip: 'bg-ok-soft text-ok', rule: 'border-l-ok' },
  watch: { dot: 'bg-watch', chip: 'bg-watch-soft text-watch', rule: 'border-l-watch' },
  signal: { dot: 'bg-signal', chip: 'bg-signal-soft text-signal', rule: 'border-l-signal' },
} as const

export type Level = keyof typeof levelStyles

/**
 * Метка оценки. Цвет дублируется формой и подписью: по одному цвету
 * состояние определять нельзя.
 */
export function LevelChip({ level, children }: { level: Level; children: ReactNode }) {
  const shape =
    level === 'ok' ? 'rounded-full' : level === 'watch' ? 'rounded-[2px]' : 'rotate-45'

  return (
    <span
      className={`inline-flex items-center gap-2 px-2.5 py-1 text-[length:var(--text-step--1)] font-semibold ${levelStyles[level].chip}`}
    >
      <span className={`size-2 ${levelStyles[level].dot} ${shape}`} aria-hidden="true" />
      {children}
    </span>
  )
}

export function levelRule(level: Level) {
  return levelStyles[level].rule
}
