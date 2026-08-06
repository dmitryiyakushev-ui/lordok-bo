import { useEffect, useRef, useState } from 'react'

/**
 * Движение на странице подчинено трём правилам:
 *
 * 1. Контент виден всегда. Прятать его умеет только скрипт, и только
 *    если движение вообще разрешено. Без JS и при отключённой анимации
 *    страница просто статична, ничего не теряется.
 * 2. Анимируются только transform и opacity, то есть композитор.
 * 3. Ничего не анимируется между человеком и кнопкой: заголовок,
 *    призыв, юридический текст и оценки триажа появляются сразу.
 */

/** Разрешено ли движение: система не просит его убрать. */
export function motionAllowed(): boolean {
  if (typeof window === 'undefined') return false
  return !window.matchMedia('(prefers-reduced-motion: reduce)').matches
}

/**
 * Сколько ждать, прежде чем показать блок без всяких условий.
 * Страховка от случая, когда наблюдатель за видимостью не сработал:
 * пустая секция на странице хуже, чем анимация не в такт.
 */
const REVEAL_FAILSAFE = 3000

/** Сработал ли элемент в зоне видимости. Срабатывает один раз. */
export function useInView<T extends Element>(rootMargin = '0px 0px -10% 0px') {
  const ref = useRef<T | null>(null)
  const [inView, setInView] = useState(() => !motionAllowed())

  useEffect(() => {
    if (!motionAllowed()) {
      setInView(true)
      return
    }
    const el = ref.current
    if (!el) return

    // Блок уже на экране в момент загрузки (герой): показываем сразу,
    // не дожидаясь колбэка наблюдателя.
    const rect = el.getBoundingClientRect()
    if (rect.top < window.innerHeight && rect.bottom > 0) {
      setInView(true)
      return
    }

    const observer = new IntersectionObserver(
      (entries) => {
        if (entries.some((e) => e.isIntersecting)) {
          setInView(true)
          observer.disconnect()
        }
      },
      { rootMargin, threshold: 0.15 },
    )
    observer.observe(el)

    const failsafe = window.setTimeout(() => {
      setInView(true)
      observer.disconnect()
    }, REVEAL_FAILSAFE)

    return () => {
      observer.disconnect()
      window.clearTimeout(failsafe)
    }
  }, [rootMargin])

  return { ref, inView }
}

/**
 * Проигрывает сцену выписки: строки по одной, затем вердикт.
 * Возвращает, сколько строк уже показано и виден ли вердикт.
 */
export function useDiaryStory(rowCount: number, active: boolean) {
  const [shown, setShown] = useState(() => (motionAllowed() ? 0 : rowCount))
  const [verdict, setVerdict] = useState(() => !motionAllowed())

  useEffect(() => {
    if (!active || !motionAllowed()) return

    const timers: number[] = []
    for (let i = 1; i <= rowCount; i += 1) {
      timers.push(window.setTimeout(() => setShown(i), i * STORY.rowStagger))
    }
    timers.push(
      window.setTimeout(
        () => setVerdict(true),
        rowCount * STORY.rowStagger + STORY.verdictPause,
      ),
    )
    return () => timers.forEach(window.clearTimeout)
  }, [active, rowCount])

  return { shown, verdict }
}

/** Счёт балла от нуля до значения, пока строка появляется. */
export function useCountUp(target: number, active: boolean) {
  const [value, setValue] = useState(() => (motionAllowed() ? 0 : target))

  useEffect(() => {
    if (!active) return
    if (!motionAllowed()) {
      setValue(target)
      return
    }

    let frame = 0
    const started = performance.now()
    const tick = (now: number) => {
      const progress = Math.min((now - started) / STORY.countDuration, 1)
      setValue(Math.round(target * progress))
      if (progress < 1) frame = requestAnimationFrame(tick)
    }
    frame = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(frame)
  }, [target, active])

  return value
}

/**
 * Тайминги сцены. Считаны от токенов kod-03: шаг между строками
 * равен --motion-fast, пауза перед вердиктом --motion-slow, счёт
 * балла укладывается в тот же шаг. Вся сцена около 0.7 секунды
 * вместо прежних 1.4.
 */
export const STORY = {
  rowStagger: 90,
  verdictPause: 200,
  countDuration: 200,
} as const
