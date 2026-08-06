import type { ElementType, ReactNode } from 'react'
import { useInView } from '../motion'

/**
 * Проявление блока при входе в зону видимости: прозрачность плюс 12 px,
 * 350 мс, power1.out. Уровень Subtle из motion-базы.
 *
 * `index` сдвигает начало для соседних карточек: 40 мс на элемент,
 * чтобы группа читалась как последовательность, а не как вспышка.
 */
export function Reveal({
  children,
  as: Tag = 'div',
  index = 0,
  className = '',
}: {
  children: ReactNode
  as?: ElementType
  index?: number
  className?: string
}) {
  const { ref, inView } = useInView<HTMLDivElement>()

  return (
    <Tag
      ref={ref}
      className={`reveal ${inView ? 'is-in' : ''} ${className}`}
      style={index ? { transitionDelay: `${index * 40}ms` } : undefined}
    >
      {children}
    </Tag>
  )
}
