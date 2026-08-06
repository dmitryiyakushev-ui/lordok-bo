import { TELEGRAM_URL } from '../data'
import { ButtonLink } from './primitives'

const navLinks = [
  { href: '#problem', label: 'Зачем' },
  { href: '#how', label: 'Как работает' },
  { href: '#doctors', label: 'Врачам' },
  { href: '#price', label: 'Цена' },
]

export function Nav() {
  return (
    <>
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:z-50 focus:bg-navy focus:px-4 focus:py-2 focus:text-paper"
      >
        Перейти к содержанию
      </a>

      <nav
        className="border-b border-line px-5 sm:px-8"
        aria-label="Основная навигация"
      >
        <div className="mx-auto flex max-w-5xl items-center justify-between gap-6 py-4">
          <a
            href="#main"
            className="inline-flex min-h-11 items-center font-display text-[length:var(--text-step-1)] font-semibold"
          >
            ЛОРдок
          </a>

          <ul className="hidden items-center gap-7 md:flex">
            {navLinks.map((l) => (
              <li key={l.href}>
                <a
                  href={l.href}
                  className="text-[length:var(--text-step--1)] text-ink-2 underline-offset-4 hover:text-ink hover:underline"
                >
                  {l.label}
                </a>
              </li>
            ))}
          </ul>

          <a
            href={TELEGRAM_URL}
            className="inline-flex min-h-11 items-center text-[length:var(--text-step--1)] font-semibold text-navy underline decoration-line underline-offset-4 hover:decoration-navy"
          >
            Открыть бот
          </a>
        </div>
      </nav>
    </>
  )
}

export function FinalCta() {
  return (
    <section className="border-t border-line bg-paper-2 px-5 sm:px-8">
      <div className="mx-auto max-w-5xl py-16 sm:py-24">
        <div className="max-w-2xl">
          <h2 className="text-[length:var(--text-step-2)] sm:text-[length:var(--text-step-3)] text-navy">
            Начните с сегодняшнего вечера
          </h2>
          <p className="mt-4 text-[length:var(--text-step-1)] text-ink-2">
            Первая запись займёт минуту. Через неделю появится динамика, а с ней
            и ответ, нужен ли визит.
          </p>
          <div className="mt-8">
            <ButtonLink href={TELEGRAM_URL}>Открыть в Telegram</ButtonLink>
          </div>
        </div>
      </div>
    </section>
  )
}

export function Footer() {
  return (
    <footer className="border-t border-line px-5 sm:px-8">
      <div className="mx-auto max-w-5xl py-10 text-[length:var(--text-step--1)] text-ink-2">
        <p className="max-w-2xl">
          ЛОРдок это информационный сервис для самонаблюдения. Не является
          медицинским изделием, не ставит диагнозов и не назначает лечения. При
          ухудшении состояния обращайтесь к врачу.
        </p>

        <div className="mt-4 flex flex-wrap items-center gap-x-6">
          <a
            href="/privacy.html"
            className="inline-flex min-h-11 items-center underline underline-offset-4 hover:text-ink"
          >
            Политика конфиденциальности
          </a>
          <a
            href="/terms.html"
            className="inline-flex min-h-11 items-center underline underline-offset-4 hover:text-ink"
          >
            Пользовательское соглашение
          </a>
          <a
            href="mailto:support@lordok.ru"
            className="inline-flex min-h-11 items-center underline underline-offset-4 hover:text-ink"
          >
            support@lordok.ru
          </a>
        </div>

        <p className="mt-6 text-ink-3">
          Оператор персональных данных: Якушев Дмитрий Игоревич, самозанятый,
          ИНН 781624864719. Данные хранятся в России и третьим лицам не
          передаются.
        </p>
      </div>
    </footer>
  )
}
