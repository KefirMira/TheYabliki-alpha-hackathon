"""Review hints only: regex matches never prove truth or financial suitability."""
import re


def financial_assertion_flags(text):
    flags=[]
    unchanged=re.compile(
        r'(?:стоимость\s+(?:кредитования|кредит[а-яё]*|за[её]мных\s+средств)|'
        r'кредитн[а-яё]*\s+ставк[а-яё]*|процентн[а-яё]*\s+расход[а-яё]*)'
        r'[^.!?;\n]{0,100}?(?:не\s+(?:меня[а-яё]*|измен[а-яё]*)|остан[а-яё]*\s+прежн[а-яё]*|неизменн[а-яё]*)')
    qualification=re.compile(r'\b(?:если|возможно|может|могут|могло|предположим)\b|'
        r'при\s+условии|нельзя\s+(?:утверждать|считать|гарантировать)|'
        r'не\s+(?:означает|гарантирует|доказывает)|некорректно\s+утверждать')
    for sentence in re.split(r'(?<=[.!?;])\s+|\n+',text.casefold()):
        if unchanged.search(sentence) and not qualification.search(sentence):
            flags.append('UNSUPPORTED_UNCHANGED_BORROWING_COST')
            break
    if re.search(r'\d+(?:[.,]\d+)?\s*(?:%|₽|руб(?:лей|ля|ль)?\b|млн\b|млрд\b|usd\b)',text.casefold()):
        flags.append('FINANCIAL_NUMBER_REQUIRES_SOURCE_REVIEW')
    return flags
