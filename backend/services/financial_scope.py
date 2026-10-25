"""Bounded lexical speech scopes, not an entailment or authorship proof."""
from dataclasses import dataclass
import re

QUALIFIED = re.compile(r'\b(?:если|возможно|может|могут|могло|предположим)\b|при\s+условии|'
    r'нельзя\s+(?:утверждать|считать|гарантировать)|не\s+(?:означает|гарантирует|доказывает)|'
    r'нет\s+оснований|не\s+подтверждено|условия[^.!?;]{0,40}неизвестн')
REJECT = re.compile(r'(?:ошибочн\w*|некорректн\w*|неверн\w*)\s+'
    r'(?:пример\w*|вывод\w*|фраз\w*|утверждени\w*)\s*:?\s*$|'
    r'(?:ошибочно|некорректно|неверно)\s+(?:утверждать|обещать|считать)\s*:?\s*$|'
    r'(?:нельзя|не\s+следует)\s+(?:утверждать|обещать)\s*:?\s*$|ошибка\s*:\s*$')
ENDORSE = re.compile(r'\bмы\s+(?:подтверждаем|согласны|поддерживаем)|это\s+верно')
FINANCIAL = re.compile(r'кредит|за[её]м|займ|доход|прибыл|убыт|долг|лизинг|ставк|плат[её]ж|погашен|экспорт|импорт')
DISTINCTION = re.compile(r'различа\w*|разгранич\w*|отдел[её]н\w*|не\s+следует\s+смешив\w*|'
    r'предполож\w*\s*,?\s*а\s+не\s+(?:установленн\w*\s+)?факт')
GUARANTEE = re.compile(r'гарантирован\w*|обеспечен\w*|неизбеж\w*|'
    r'при\s+(?:любом|любых)\s+(?:сценари\w*|услови\w*)|убыт\w*\s+исключ[её]н\w*|без\s+риск\w*')
OUTCOME = re.compile(r'\b(?:доход\w*|прибыл\w*|убыт\w*|безубыточн\w*)\b')
NEGATED_GUARANTEE = re.compile(r'не\s+(?:гарантирован\w*|обеспечен\w*)|нет\s+гаранти\w*|'
    r'(?:нельзя|никто\s+не\s+может|не\s+следует)\s+(?:гарантиров\w*|обеща\w*)|'
    r'не\s+исключ[её]н\w*\s+убыт\w*')
CONTRACT_OBJECT = re.compile(r'услови\w*\s+(?:кредит\w*|займ\w*|за[её]м\w*)|'
    r'график\w*[^.!?;]{0,45}(?:погашен\w*|выплат\w*|плат[её]ж\w*)')
ESTABLISHED = re.compile(r'установлен\w*|согласован\w*|утвержд[её]н\w*|предусмотрен\w*|определ[её]н\w*')


@dataclass(frozen=True)
class SpeechSpan:
    text: str
    start: int
    end: int
    mode: str


def is_meta_distinction(text):
    lower=text.casefold()
    return bool(re.search(r'факт|по\s+данным\s+профиля',lower)
        and re.search(r'предполож|гипотез',lower) and DISTINCTION.search(lower)
        and not FINANCIAL.search(lower))


def _clauses(text, start, end, forced=None):
    fragment=text[start:end]
    cursor=0
    for match in [*re.finditer(r'(?<=[.!?;])\s+|\n+|\s+(?=но\s+|однако\s+)',fragment),None]:
        stop=match.start() if match else len(fragment)
        raw=fragment[cursor:stop]
        left=len(raw)-len(raw.lstrip())
        right=len(raw.rstrip())
        if right>left:
            value=raw[left:right]
            mode=forced or ('META_DISTINCTION' if is_meta_distinction(value) else
                'CONDITIONAL' if QUALIFIED.search(value.casefold()) else 'AUTHOR_ASSERTION')
            yield SpeechSpan(value,start+cursor+left,start+cursor+right,mode)
        cursor=match.end() if match else len(fragment)


def speech_spans(text):
    if len(text)>100_000:raise ValueError('FINANCIAL_SCOPE_INPUT_TOO_LARGE')
    pairs={'«':'»','“':'”','"':'"'}
    stack=[]
    ranges=[]
    opening=0
    nested=False
    for index,char in enumerate(text):
        if stack and char==stack[-1]:
            stack.pop()
            if not stack:ranges.append((opening,index+1,nested))
        elif char in pairs:
            if not stack:opening=index; nested=False
            else:nested=True
            stack.append(pairs[char])
        elif char in {'»','”'}:
            if stack:nested=True
            else:ranges.append((index,index+1,True))
    if stack:ranges.append((opening,len(text),True))
    result=[]
    cursor=0
    for start,end,uncertain in ranges:
        result.extend(_clauses(text,cursor,start))
        prefix=text[max(0,start-180):start].casefold()
        tail=text[end:end+120].casefold()
        rejected=not uncertain and REJECT.search(prefix) and not ENDORSE.search(tail)
        result.extend(_clauses(text,start,end,'REJECTED_QUOTE' if rejected else 'UNRESOLVED'))
        cursor=end
    result.extend(_clauses(text,cursor,len(text)))
    if len(result)>512:raise ValueError('FINANCIAL_SCOPE_SPAN_LIMIT')
    return result


def unconditional_outcome(text):
    lower=text.casefold()
    return bool(OUTCOME.search(lower) and GUARANTEE.search(lower)
        and not NEGATED_GUARANTEE.search(lower)
        and not re.search(r'нельзя\s+утверждать|неверно\s+утверждать|нет\s+оснований',lower))


def contract_grounding_required(text):
    lower=text.casefold()
    # Current company-context-v1 has no permissible verified terms/schedule projection.
    # A matching source or injected arbitrary context key cannot fill this requirement.
    return bool(CONTRACT_OBJECT.search(lower) and ESTABLISHED.search(lower) and not QUALIFIED.search(lower))
