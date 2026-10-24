"""Review hints only: regex matches never prove truth or financial suitability."""
import re


def financial_assertion_flags(text):
    flags=[]
    cost=(r'(?:стоимост[ьи]\s+(?:кредитования|кредит[а-яё]*|'
          r'за[её]мн[а-яё]*\s+(?:средств|финансирован[а-яё]*))|'
          r'кредитн[а-яё]*\s+ставк[а-яё]*|процентн[а-яё]*\s+расход[а-яё]*)')
    gap=r'[^.!?;\n]{0,100}?'
    unchanged=re.compile(
        cost+gap+r'(?:не\s+(?:меня[а-яё]*|измен[а-яё]*)|'
        r'оста[а-яё]*\s+(?:прежн[а-яё]*|на\s+прежн[а-яё]*\s+уровне)|неизменн[а-яё]*)|'
        r'изменени[еяй]'+gap+cost+gap+r'(?:не\s+(?:произош[а-яё]*|было)|отсутству[а-яё]*)|'
        r'не\s+(?:произош[а-яё]*|наблюда[а-яё]*|было)'+gap+r'изменени[еяй]'+gap+cost)
    qualification=re.compile(r'\b(?:если|возможно|может|могут|могло|предположим)\b|'
        r'при\s+условии|нельзя\s+(?:утверждать|считать|гарантировать)|'
        r'не\s+(?:означает|гарантирует|доказывает)|(?:некорректно|неверно)\s+утверждать|'
        r'нет\s+оснований\s+утверждать|не\s+подтверждено')
    for sentence in re.split(r'(?<=[.!?;])\s+|\n+',text.casefold()):
        if unchanged.search(sentence) and not qualification.search(sentence):
            flags.append('UNSUPPORTED_UNCHANGED_BORROWING_COST')
            break
    if re.search(r'\d+(?:[.,]\d+)?\s*(?:%|₽|руб(?:лей|ля|ль)?\b|млн\b|млрд\b|usd\b)',text.casefold()):
        flags.append('FINANCIAL_NUMBER_REQUIRES_SOURCE_REVIEW')
    return flags
