import { useEffect, useRef, useState } from 'react'
import { motionAllowed } from './motion'
import { progressFor } from './progress'

/**
 * Прогресс прохождения блока через экран: 0 в момент, когда блок
 * только показался снизу, 1 когда он ушёл в верхнюю треть.
 *
 * Считается на scroll с привязкой к кадру, поэтому обработчик не
 * трогает layout чаще, чем экран успевает перерисоваться. Если
 * движение отключено или скрипта нет, прогресс сразу равен единице:
 * график виден целиком, ничего не теряется.
 */
export function useScrollProgress<T extends HTMLElement>() {
  const ref = useRef<T | null>(null)
  const [progress, setProgress] = useState(() => (motionAllowed() ? 0 : 1))

  useEffect(() => {
    if (!motionAllowed()) {
      setProgress(1)
      return
    }
    const el = ref.current
    if (!el) return

    let frame = 0
    const measure = () => {
      frame = 0
      setProgress(progressFor(el.getBoundingClientRect().top, window.innerHeight))
    }

    const onScroll = () => {
      if (!frame) frame = requestAnimationFrame(measure)
    }

    measure()
    window.addEventListener('scroll', onScroll, { passive: true })
    window.addEventListener('resize', onScroll, { passive: true })
    return () => {
      window.removeEventListener('scroll', onScroll)
      window.removeEventListener('resize', onScroll)
      if (frame) cancelAnimationFrame(frame)
    }
  }, [])

  return { ref, progress }
}
