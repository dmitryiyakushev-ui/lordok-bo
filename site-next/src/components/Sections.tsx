import { FileText, ShieldCheck } from 'lucide-react'
import {
  TELEGRAM_URL,
  doctorReport,
  problems,
  steps,
  triageStates,
} from '../data'
import { ButtonLink, LevelChip, Section } from './primitives'
import { Reveal } from './Reveal'

export function Problem() {
  return (
    <Section
      id="problem"
      eyebrow="Почему это нужно"
      title="Хроническая ЛОР-болезнь живёт между приёмами, а наблюдают её только на приёме"
      lede="Мы провели 18 глубинных интервью с пациентами и три с ЛОР-врачами. Три вещи повторялись почти у всех."
    >
      <div className="mt-10 grid gap-px bg-line sm:grid-cols-3">
        {problems.map((p, i) => (
          <Reveal as="article" key={p.title} index={i} className="bg-paper p-6">
            <h3 className="text-[length:var(--text-step-1)]">{p.title}</h3>
            <p className="mt-3 text-ink-2">{p.body}</p>
            <p className="mt-4 border-t border-line pt-3 text-[length:var(--text-step--1)] text-ink-3">
              {p.source}
            </p>
          </Reveal>
        ))}
      </div>
    </Section>
  )
}

export function HowItWorks() {
  return (
    <Section
      id="how"
      eyebrow="Как это работает"
      title="Четыре шага, тридцать секунд в день"
    >
      <ol className="mt-10 grid gap-px bg-line sm:grid-cols-2">
        {steps.map((s, i) => (
          <Reveal as="li" key={s.n} index={i} className="bg-paper p-6 sm:p-8">
            <span className="font-display text-[length:var(--text-step-2)] text-ink-3 tabular">
              {s.n}
            </span>
            <h3 className="mt-2 text-[length:var(--text-step-1)]">{s.title}</h3>
            <p className="mt-3 max-w-md text-ink-2">{s.body}</p>
          </Reveal>
        ))}
      </ol>
    </Section>
  )
}

export function Triage() {
  return (
    <Section
      id="triage"
      eyebrow="Что именно отвечает бот"
      title="Не диагноз, а решение о визите"
      lede="После кастдева мы отказались от идеи предварительного диагноза: 13 из 18 участников боялись получить неверный. Осталось три ответа."
    >
      <div className="mt-10 grid gap-px bg-line sm:grid-cols-3">
        {triageStates.map((t) => (
          <article key={t.level} className="bg-paper p-6">
            <LevelChip level={t.level}>{t.label}</LevelChip>
            <p className="mt-4 text-ink-2">{t.body}</p>
          </article>
        ))}
      </div>

      <p className="mt-8 flex max-w-2xl items-start gap-3 text-[length:var(--text-step--1)] text-ink-2">
        <ShieldCheck className="mt-0.5 size-5 shrink-0 text-navy" aria-hidden="true" />
        <span>
          Алгоритм собран практикующим оториноларингологом по EPOS 2020,
          рекомендациям AAO-HNS и AAP. Тревожные признаки проверяются раньше
          всех прочих правил и никогда не понижаются.
        </span>
      </p>
    </Section>
  )
}

export function ForDoctors() {
  return (
    <Section
      id="doctors"
      eyebrow="Врачам"
      title="Пациент приходит с выпиской, а не с пересказом"
    >
      <div className="mt-10 grid gap-10 lg:grid-cols-2 lg:gap-16">
        <div>
          <p className="text-ink-2">
            Пациент присылает PDF перед приёмом или показывает с телефона.
            Данные собраны им самим, ежедневно, в одном формате, поэтому
            сравнимы между визитами.
          </p>
          <ul className="mt-6 space-y-3">
            {doctorReport.map((item) => (
              <li key={item} className="flex items-start gap-3">
                <FileText
                  className="mt-1 size-4 shrink-0 text-navy"
                  aria-hidden="true"
                />
                <span className="text-ink-2">{item}</span>
              </li>
            ))}
          </ul>
        </div>

        <blockquote className="border-l-2 border-navy pl-6">
          <p className="font-display text-[length:var(--text-step-1)] italic leading-snug">
            «Я не хочу, чтобы приложение говорило мне, что у меня. Я хочу
            понимать, пора к врачу или нет. Это разные вещи».
          </p>
          <footer className="mt-4 text-[length:var(--text-step--1)] text-ink-3">
            Участник кастдева, 44 года, хронический риносинусит
          </footer>
        </blockquote>
      </div>
    </Section>
  )
}

export function Price() {
  return (
    <Section id="price" eyebrow="Сколько стоит" title="Сейчас бесплатно">
      <div className="mt-8 max-w-2xl">
        <p className="text-ink-2">
          Дневник, оценка динамики, тревожные признаки и сводка за неделю
          доступны без оплаты. Мы не берём денег, пока не убедимся, что люди
          возвращаются в бот второй и третий раз.
        </p>
        <p className="mt-4 text-ink-2">
          Полная версия отчёта с графиками, шкалами и историей за любой период
          готовится. Когда она появится, о цене скажем заранее, а собранные
          данные останутся вашими в любом случае.
        </p>
        <div className="mt-8">
          <ButtonLink href={TELEGRAM_URL}>Открыть в Telegram</ButtonLink>
        </div>
      </div>
    </Section>
  )
}

export function Author() {
  return (
    <Section id="author" eyebrow="Кто сделал" title="Практикующий ЛОР-врач">
      <div className="mt-8 max-w-2xl">
        <p className="text-ink-2">
          Дмитрий Якушев, оториноларинголог, главный ЛОР-специалист сети клиник
          «Фомина». Идея выросла из приёма: пациенты приходят уже с обострением,
          потому что между визитами им не с чем сверяться.
        </p>
        <p className="mt-4 text-ink-2">
          Вопросы дневника, пороги и формулировки ответов написаны им же, а не
          заимствованы из общих симптом-чекеров.
        </p>
      </div>
    </Section>
  )
}
