/**
 * Прогресс прохождения блока через экран, без React и без DOM.
 *
 * 0: верх блока стоит на 85% высоты экрана, то есть блок только
 *    показался снизу.
 * 1: верх блока поднялся до 25% высоты, блок прочитан.
 */
export function progressFor(rectTop: number, viewportHeight: number): number {
  const start = viewportHeight * 0.85
  const end = viewportHeight * 0.25
  const raw = (start - rectTop) / (start - end)
  return Math.min(1, Math.max(0, raw))
}
