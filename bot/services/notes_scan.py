"""Разбор свободной заметки пациента на тревожные признаки.

Раньше это был поиск подстрок: «крови нет» и «боюсь крови» поднимали
красный флаг наравне с «идёт кровь». Здесь текст разбирается на слова,
ключевые фразы сопоставляются по основам (задыха → задыхаюсь,
задыхался), а отрицания рядом с находкой её снимают.

Модуль намеренно без зависимостей: его можно гонять тестами отдельно
от бота и базы.
"""

import re
from typing import List, Optional, Tuple

# Каждый вложенный список это ИЛИ-группа: сработала любая фраза,
# сработала вся группа. Слова записаны основами без окончаний.
ESCALATION_RED: List[List[List[str]]] = [
    [["не", "могу", "дыша"], ["задыха"], ["удуш"]],
    [["потер", "сознан"], ["теря", "сознан"], ["обморок"]],
    [["не", "могу", "глота"], ["невозможно", "глота"]],
    [["не", "могу", "открыть", "рот"]],
    [["кровотеч"], ["кровь", "теч"], ["хлещет", "кровь"]],
    [["скор", "помощь"], ["реанимац"]],
    [["судорог"]],
    [["отек", "горл"], ["горло", "отекл"]],
]

ESCALATION_YELLOW: List[List[List[str]]] = [
    [["стало", "хуже"], ["ухудшен"], ["резко", "ухудш"]],
    [["гно"]],
    [["лечен", "не", "помога"], ["антибиотик", "не", "помога"]],
    [["сильн", "боль"], ["невыносим", "боль"]],
    [["температур", "не", "снижа"], ["температур", "не", "сбива"],
     ["жаропонижа", "не", "помога"]],
    [["рвот"], ["тошнот"]],
    [["отек", "лиц"], ["опухло", "лицо"], ["опухла", "щек"]],
    [["шум", "в", "ух"], ["звон", "в", "ух"]],
    [["головокружен"], ["кружит", "голов"], ["кружил", "голов"]],
    [["кровь", "из", "ух"], ["кровь", "из", "нос"]],
]

# Слова, которые отменяют находку, если стоят перед ней.
NEGATIONS_BEFORE = {
    "не", "нет", "без", "никогда", "боюсь", "боялся", "опасаюсь",
    "прошло", "прошла", "прошли", "прекратилось", "перестало",
}
# Отрицание после находки должно стоять вплотную: «рвоты нет».
NEGATIONS_AFTER = {
    "нет", "прошло", "прошла", "прошли", "прекратилось", "перестало",
    "исчезло",
}
NEGATION_AFTER_PAIR = {"было", "бывает", "бывало", "беспокоит"}

# Сколько слов слева смотреть на отрицание (в пределах своей части фразы).
WINDOW_BEFORE = 3

# Основы короче этого совпадают только целым словом: «не» не должно
# цепляться за «нет», «нельзя» и прочее.
MIN_PREFIX_LEN = 3

_TOKEN_RE = re.compile(r"[а-яa-z0-9]+")

# Границы частей предложения. Окно отрицания их не пересекает, иначе
# «гной, температура не снижается» снимает флаг с гноя.
_CLAUSE_SPLIT_RE = re.compile(r"[.,;:!?\n]+|\bно\b|\bхотя\b|\bзато\b")


def tokenize(text: str) -> List[str]:
    """Текст в список слов: нижний регистр, ё сводится к е."""
    return _TOKEN_RE.findall(text.lower().replace("ё", "е"))


def split_clauses(text: str) -> List[List[str]]:
    """Разбить текст на части предложения и каждую на слова."""
    normalized = text.lower().replace("ё", "е")
    chunks = _CLAUSE_SPLIT_RE.split(normalized)
    return [tokens for tokens in (tokenize(c) for c in chunks) if tokens]


def _token_matches(token: str, stem: str) -> bool:
    if len(stem) < MIN_PREFIX_LEN:
        return token == stem
    return token.startswith(stem)


def _find_phrase(tokens: List[str], phrase: List[str]) -> Optional[Tuple[int, int]]:
    """Позиция фразы в тексте как (начало, конец) в словах."""
    if not phrase or len(phrase) > len(tokens):
        return None
    for i in range(len(tokens) - len(phrase) + 1):
        if all(
            _token_matches(tokens[i + j], stem) for j, stem in enumerate(phrase)
        ):
            return i, i + len(phrase)
    return None


def _is_negated(tokens: List[str], start: int, end: int) -> bool:
    """Стоит ли рядом с находкой отрицание.

    Отрицание внутри самой фразы («не могу дышать») не считается:
    смотрим только соседей слева и справа.
    """
    before = tokens[max(0, start - WINDOW_BEFORE):start]
    if any(t in NEGATIONS_BEFORE for t in before):
        return True

    if end < len(tokens):
        if tokens[end] in NEGATIONS_AFTER:
            return True
        if (
            tokens[end] == "не"
            and end + 1 < len(tokens)
            and tokens[end + 1] in NEGATION_AFTER_PAIR
        ):
            return True

    return False


def _scan(clauses: List[List[str]], groups: List[List[List[str]]]) -> List[str]:
    """Все сработавшие фразы из набора групп."""
    matched: List[str] = []
    for group in groups:
        for phrase in group:
            hit = False
            for tokens in clauses:
                span = _find_phrase(tokens, phrase)
                if span is None:
                    continue
                if _is_negated(tokens, *span):
                    continue
                hit = True
                break
            if hit:
                matched.append(" ".join(phrase))
                break  # группа сработала, остальные варианты не нужны
    return matched


def scan_notes(text: str) -> Tuple[Optional[str], List[str]]:
    """Разобрать заметку.

    Returns
    -------
    (уровень, сработавшие фразы)
        уровень: "red", "yellow" или None
    """
    if not text:
        return None, []

    clauses = split_clauses(text)
    if not clauses:
        return None, []

    red = _scan(clauses, ESCALATION_RED)
    if red:
        return "red", red[:1]

    yellow = _scan(clauses, ESCALATION_YELLOW)
    if yellow:
        return "yellow", yellow

    return None, []
