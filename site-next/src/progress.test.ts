import { progressFor } from './progress.ts'

const vh = 1000
const cases: [string, number, number][] = [
  ['блок ещё под экраном', 1200, 0],
  ['верх блока на 85% экрана', 850, 0],
  ['ровно посередине хода', 550, 0.5],
  ['верх блока на 25% экрана', 250, 1],
  ['блок ушёл вверх', -400, 1],
  ['экран другой высоты, середина', 275, 0.5],
]

let bad = 0
for (const [name, top, expected] of cases) {
  const height = name.includes('другой высоты') ? 500 : vh
  const got = +progressFor(top, height).toFixed(3)
  const ok = Math.abs(got - expected) < 0.001
  if (!ok) bad += 1
  console.log(`${ok ? 'ок  ' : 'СБОЙ'} ${name}: ждали ${expected}, получили ${got}`)
}
console.log(bad ? `провалов: ${bad}` : 'все проверки прошли')
process.exit(bad ? 1 : 0)
