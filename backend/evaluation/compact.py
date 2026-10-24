"""Opt-in evaluation instructions; no public schema or production prompt change."""
VARIANT='comparison-compact-v1'
RULES='''
Формат краткого тестового ответа (те же обязательные JSON-поля):
- summary: до 2 коротких предложений, до 240 символов: факт новости и значимый признак компании.
- risks: до 2 пунктов; opportunities: до 1; recommendations: до 2. Каждый пункт до 140 символов.
- Целевой объём всего JSON — до 1400 символов. Без отступов и повторения одних оговорок в разных полях.
- Укажи неизвестность условий один раз; гипотезы и действия формулируй условно. Пустые списки допустимы.
- Ссылки [Источник N] ставь только к тезисам, подтверждённым RAG; не приписывай RAG факты новости или профиля.
- Не выводи неизменность стоимости кредитования из неизменной ключевой ставки: договорные условия неизвестны.
- Не добавляй поля, цифры или факты. Верни только итоговый JSON, без пояснений вне него.
'''


def output_checks(content, raw=None):
    violations=[]
    if len(content.summary)>240:violations.append('SUMMARY_OVER_240_CHARACTERS')
    for field,limit in [('risks',2),('opportunities',1),('recommendations',2)]:
        values=getattr(content,field)
        if len(values)>limit:violations.append(field.upper()+'_TOO_MANY_ITEMS')
        if any(len(value)>140 for value in values):violations.append(field.upper()+'_ITEM_OVER_140_CHARACTERS')
    characters=len(raw) if raw is not None else len(content.model_dump_json())
    if characters>1400:violations.append('JSON_OVER_1400_CHARACTERS')
    return {'variant':VARIANT,'violations':violations,'raw_characters':characters,'human_review_required':True}
