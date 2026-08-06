import { TELEGRAM_URL, diaryExtract } from '../data'
import { useCountUp, useDiaryStory, useInView } from '../motion'
import { ButtonLink, Eyebrow, LevelChip, levelRule, type Level } from './primitives'

/**
 * Первый экран. Заголовок, текст и кнопки не анимируются: между
 * человеком и переходом в бот ничего стоять не должно.
 *
 * Двигается только выписка, и только один раз. За полторы секунды она
 * проигрывает неделю: строки по одной, балл набегает, левая полоса
 * меняет цвет по дням, в конце появляется вердикт. Это единственное
 * место, где движение объясняет продукт, а не украшает страницу.
 */
export function Hero() {
  const { ref, inView } = useInView<HTMLElement>()
  const { shown, verdict } = useDiaryStory(diaryExtract.length, inView)

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

          <figure ref={ref} className="m-0 border border-line bg-paper-2">
            <figcaption className="flex items-baseline justify-between border-b border-line px-4 py-3">
              <span className="font-display text-[length:var(--text-step-0)] font-semibold">
                Выписка за неделю
              </span>
              <span className="text-[length:var(--text-step--1)] text-ink-3">
                риносинусит
              </span>
            </figcaption>

            <ul className="divide-y divide-line">
              {diaryExtract.map((row, i) => (
                <DiaryRow key={row.day} {...row} shown={i < shown} />
              ))}
            </ul>

            <div
              className={`row-enter border-t border-line px-4 py-3 ${
                verdict ? 'is-in' : ''
              }`}
            >
              <LevelChip level="signal">К врачу сегодня</LevelChip>
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

function DiaryRow({
  day,
  score,
  verdict,
  note,
  shown,
}: {
  day: string
  score: number
  verdict: Level
  note: string
  shown: boolean
}) {
  const value = useCountUp(score, shown)

  return (
    <li
      className={`row-enter border-l-2 ${levelRule(verdict)} px-4 py-3 ${
        shown ? 'is-in' : ''
      }`}
    >
      <div className="flex items-baseline justify-between gap-3">
        <span className="tabular text-[length:var(--text-step--1)] text-ink-2">
          {day}
        </span>
        <span className="tabular text-[length:var(--text-step--1)] text-ink-3">
          балл {value}
        </span>
      </div>
      <p className="mt-1 text-[length:var(--text-step--1)] leading-snug">{note}</p>
    </li>
  )
}
