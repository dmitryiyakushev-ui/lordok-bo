import { diaryExtract } from '../data'
import { useScrollProgress } from '../useScrollProgress'
import { LevelChip, Section, type Level } from './primitives'

/**
 * Кривая недели, которую рисует скролл.
 *
 * Это та же неделя, что в выписке на первом экране, только показанная
 * как динамика: линия дорисовывается по мере прокрутки, точки дней
 * загораются одна за другой, а когда кривая заходит в верхнюю зону,
 * появляется вердикт.
 *
 * Смысл ровно в этом: продукт про то, что решение принимается по
 * тренду, а не по одному дню. Здесь тренд можно проскроллить руками.
 *
 * Без скрипта и при отключённой анимации график сразу нарисован
 * целиком, вместе с вердиктом.
 */

const W = 640
const H = 260
const PAD = { top: 28, right: 24, bottom: 34, left: 34 }

const MAX_SCORE = 16
const WATCH_AT = 9   // с этого балла оценка становится жёлтой
const SIGNAL_AT = 12 // с этого балла красной

const points = diaryExtract.map((row, i) => ({
  ...row,
  x: PAD.left + (i * (W - PAD.left - PAD.right)) / (diaryExtract.length - 1),
  y: PAD.top + (1 - row.score / MAX_SCORE) * (H - PAD.top - PAD.bottom),
}))

const linePath = points
  .map((p, i) => `${i === 0 ? 'M' : 'L'} ${p.x.toFixed(1)} ${p.y.toFixed(1)}`)
  .join(' ')

const yFor = (score: number) =>
  PAD.top + (1 - score / MAX_SCORE) * (H - PAD.top - PAD.bottom)

export function WeekChart() {
  const { ref, progress } = useScrollProgress<HTMLDivElement>()

  // Линия рисуется первые 75% прогресса, дальше место для вердикта.
  const draw = Math.min(1, progress / 0.75)
  const shownPoints = Math.round(draw * (points.length - 1))
  const verdictIn = progress > 0.82

  return (
    <Section
      id="week"
      eyebrow="Что видит алгоритм"
      title="Решение принимается по неделе, а не по одному дню"
      lede="Это та же неделя, что в выписке выше. Прокрутите, и станет видно, как она набирает вес."
    >
      <div ref={ref} className="mt-10 border border-line bg-paper-2 p-4 sm:p-6">
        <svg
          viewBox={`0 0 ${W} ${H}`}
          className="w-full"
          role="img"
          aria-label="График суммарной тяжести симптомов за пять дней: 7, 8, 10, 11 и 13 баллов. На пятый день оценка становится красной."
        >
          {/* Зоны оценки: жёлтая и красная. Дублируют цвет подписью. */}
          <rect
            x={PAD.left}
            y={yFor(SIGNAL_AT)}
            width={W - PAD.left - PAD.right}
            height={yFor(WATCH_AT) - yFor(SIGNAL_AT)}
            className="fill-watch-soft"
          />
          <rect
            x={PAD.left}
            y={PAD.top}
            width={W - PAD.left - PAD.right}
            height={yFor(SIGNAL_AT) - PAD.top}
            className="fill-signal-soft"
          />

          <text
            x={PAD.left + 8}
            y={PAD.top + 14}
            className="fill-signal text-[10px]"
            style={{ fontSize: 10 }}
          >
            к врачу сегодня
          </text>
          <text
            x={PAD.left + 8}
            y={yFor(SIGNAL_AT) + 13}
            className="fill-watch text-[10px]"
            style={{ fontSize: 10 }}
          >
            к врачу планово
          </text>

          {/* Оси: только две линии, сетку не рисуем. */}
          <line
            x1={PAD.left}
            y1={H - PAD.bottom}
            x2={W - PAD.right}
            y2={H - PAD.bottom}
            className="stroke-line"
            strokeWidth="1"
          />
          <line
            x1={PAD.left}
            y1={PAD.top}
            x2={PAD.left}
            y2={H - PAD.bottom}
            className="stroke-line"
            strokeWidth="1"
          />

          {/* Сама кривая: длина штриха привязана к прогрессу. */}
          <path
            d={linePath}
            fill="none"
            className="stroke-navy"
            strokeWidth="2.5"
            strokeLinecap="round"
            strokeLinejoin="round"
            pathLength={1}
            style={{ strokeDasharray: 1, strokeDashoffset: 1 - draw }}
          />

          {/* Точки дней загораются по очереди. */}
          {points.map((p, i) => {
            const on = i <= shownPoints
            const color =
              p.verdict === 'signal'
                ? 'fill-signal'
                : p.verdict === 'watch'
                  ? 'fill-watch'
                  : 'fill-ok'
            return (
              <g
                key={p.day}
                style={{
                  opacity: on ? 1 : 0,
                  transition: 'opacity var(--motion-fast) var(--ease-out)',
                }}
              >
                <circle cx={p.x} cy={p.y} r="5" className={color} />
                <circle cx={p.x} cy={p.y} r="9" className={color} opacity="0.18" />
                <text
                  x={p.x}
                  y={H - PAD.bottom + 16}
                  textAnchor="middle"
                  className="fill-ink-3"
                  style={{ fontSize: 11 }}
                >
                  {p.day.split(' ')[0]}
                </text>
                <text
                  x={p.x}
                  y={p.y - 14}
                  textAnchor="middle"
                  className="fill-ink-2 tabular"
                  style={{ fontSize: 12, fontWeight: 600 }}
                >
                  {p.score}
                </text>
              </g>
            )
          })}
        </svg>

        <div
          className="row-enter mt-4 flex flex-wrap items-center gap-3 border-t border-line pt-4"
          style={{ opacity: verdictIn ? 1 : 0 }}
        >
          <LevelChip level={'signal' as Level}>К врачу сегодня</LevelChip>
          <p className="max-w-md text-[length:var(--text-step--1)] text-ink-2">
            Пятые сутки роста без улучшения. Один такой день ничего не значит,
            неделя такого роста значит.
          </p>
        </div>
      </div>
    </Section>
  )
}
