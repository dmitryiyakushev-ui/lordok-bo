import { TELEGRAM_URL, diaryExtract } from '../data'
import { ButtonLink, Eyebrow, LevelChip, levelRule } from './primitives'

const verdictLabel = {
  ok: 'Наблюдаем',
  watch: 'К врачу планово',
  signal: 'К врачу сегодня',
} as const

/**
 * Первый экран. Вместо мокапа чата показываем то, ради чего продукт
 * существует: выписку из дневника, где видно, как неделя доходит до
 * рекомендации.
 */
export function Hero() {
  return (
    <header className="px-5 sm:px-8">
      <div className="mx-auto max-w-5xl pt-10 pb-14 sm:pt-16 sm:pb-20 lg:pb-28">
        <div className="grid gap-12 lg:grid-cols-[minmax(0,1fr)_22rem] lg:gap-16 lg:items-start">
          <div>
            <Eyebrow>Дневник ЛОР-симптомов в Telegram</Eyebrow>
            <h1 className="mt-4 text-[length:var(--text-step-3)] sm:text-[length:var(--text-step-4)] text-navy">
              Между визитами к врачу пациент остаётся один
            </h1>
            <p className="mt-6 max-w-xl text-[length:var(--text-step-1)] leading-relaxed text-ink-2">
              ЛОРдок ведёт дневник симптомов, показывает динамику и отвечает на
              единственный вопрос, который волнует между приёмами: идти к врачу
              сейчас или можно наблюдать.
            </p>
            <p className="mt-4 max-w-xl text-ink-2">
              Диагнозов не ставит и врача не заменяет. Оценка строится на
              клинических рекомендациях, а не на догадках.
            </p>

            <div className="mt-9 flex flex-wrap items-center gap-x-6 gap-y-3">
              <ButtonLink href={TELEGRAM_URL}>Открыть в Telegram</ButtonLink>
              <ButtonLink href="#how" variant="quiet">
                Как это работает
              </ButtonLink>
            </div>

            <p className="mt-6 text-[length:var(--text-step--1)] text-ink-3">
              Бесплатно. Приложение ставить не нужно.
            </p>
          </div>

          {/* Специмен выписки */}
          <figure className="m-0 border border-line bg-paper-2">
            <figcaption className="flex items-baseline justify-between border-b border-line px-4 py-3">
              <span className="font-display text-[length:var(--text-step-0)] font-semibold">
                Выписка за неделю
              </span>
              <span className="text-[length:var(--text-step--1)] text-ink-3">
                риносинусит
              </span>
            </figcaption>

            <ul className="divide-y divide-line">
              {diaryExtract.map((row) => (
                <li
                  key={row.day}
                  className={`border-l-2 ${levelRule(row.verdict)} px-4 py-3`}
                >
                  <div className="flex items-baseline justify-between gap-3">
                    <span className="tabular text-[length:var(--text-step--1)] text-ink-2">
                      {row.day}
                    </span>
                    <span className="tabular text-[length:var(--text-step--1)] text-ink-3">
                      балл {row.score}
                    </span>
                  </div>
                  <p className="mt-1 text-[length:var(--text-step--1)] leading-snug">
                    {row.note}
                  </p>
                </li>
              ))}
            </ul>

            <div className="border-t border-line px-4 py-3">
              <LevelChip level="signal">{verdictLabel.signal}</LevelChip>
              <p className="mt-2 text-[length:var(--text-step--1)] leading-snug text-ink-2">
                Пятые сутки без улучшения плюс подъём температуры. Это повод
                показаться ЛОР-врачу в ближайшие сутки.
              </p>
            </div>
          </figure>
        </div>
      </div>
    </header>
  )
}
