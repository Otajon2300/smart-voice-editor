"""Text normalisation shared by the script and the recognised speech.

Both sides are reduced to the same lower-case Latin tokens so that Cyrillic
and Latin spellings, apostrophe variants and written numbers compare equal.
"""
import re
import unicodedata

CYRILLIC = dict(zip(
    'абвгдеёжзийклмнопрстуфхцчшщъыьэюяқғҳў',
    ['a', 'b', 'v', 'g', 'd', 'e', 'yo', 'j', 'z', 'i', 'y', 'k', 'l', 'm', 'n', 'o', 'p', 'r', 's', 't',
     'u', 'f', 'x', 'ts', 'ch', 'sh', 'sh', "'", 'i', '', 'e', 'yu', 'ya', 'q', "g'", 'h', "o'"]))
APOSTROPHES = '‘’ʻʼ`´'
TOKEN = re.compile(r"[^\W_]+(?:'[^\W_]+)*", re.UNICODE)

UNITS = ['nol', 'bir', 'ikki', 'uch', "to'rt", 'besh', 'olti', 'yetti', 'sakkiz', "to'qqiz"]
TENS = ['', "o'n", 'yigirma', "o'ttiz", 'qirq', 'ellik', 'oltmish', 'yetmish', 'sakson', "to'qson"]
# Roman numerals II..XXXIX. Single letters are numerals only before a word such as "asr" or a hyphen.
ROMAN_RE = re.compile(r'\b(?=[IVX]{2,}\b)X{0,3}(?:IX|IV|V?I{0,3})\b|\b[IVX]\b(?=\s*-|\s+(?:asr|аср|chorak|чорак))')
ROMAN_VALUES = {'I': 1, 'V': 5, 'X': 10}
ABBREVIATIONS = {'mln': 'million', 'mlrd': 'milliard', 'trln': 'trillion'}
FRACTIONS = {1: "o'ndan", 2: 'yuzdan', 3: 'mingdan'}
# "1 500 000" and "1.500.000" are one number; "3,5" is "uch butun o'ndan besh".
GROUPED = re.compile(r'(?<![\d.,])\d{1,3}(?:[   ]\d{3})+(?![\d])|(?<![\d.,])\d{1,3}(?:\.\d{3}){2,}(?![\d.,])')
DECIMAL = re.compile(r'(?<![\d.,])(\d+),(\d{1,3})(?![\d,])')


PERCENT = re.compile(r'(\d+)(,\d+)?\s*%')

# Russian. Words are spelled with "е" for "ё", as most scripts and the recogniser write them.
RU_ONES = ('ноль один два три четыре пять шесть семь восемь девять десять одиннадцать двенадцать тринадцать '
           'четырнадцать пятнадцать шестнадцать семнадцать восемнадцать девятнадцать').split()
RU_TENS = ' . двадцать тридцать сорок пятьдесят шестьдесят семьдесят восемьдесят девяносто'.split(' ')
RU_HUNDREDS = ' сто двести триста четыреста пятьсот шестьсот семьсот восемьсот девятьсот'.split(' ')
RU_SCALES = [(10 ** 9, ('миллиард', 'миллиарда', 'миллиардов')), (10 ** 6, ('миллион', 'миллиона', 'миллионов')),
             (1000, ('тысяча', 'тысячи', 'тысяч'))]
# Ordinal stems; "*" marks the stressed ending (второй, шестой), "~" the soft one (третий, третьего).
RU_ORDINALS = dict(zip(RU_ONES, 'нулев* перв втор* трет~ четверт пят шест* седьм* восьм* девят десят одиннадцат '
                                'двенадцат тринадцат четырнадцат пятнадцат шестнадцат семнадцат восемнадцат '
                                'девятнадцат'.split()))
RU_ORDINALS.update(zip(RU_TENS[2:], 'двадцат тридцат сороков* пятидесят шестидесят семидесят восьмидесят девяност'.split()))
RU_ORDINALS.update(zip(RU_HUNDREDS[1:], 'сот двухсот трехсот четырехсот пятисот шестисот семисот восьмисот девятисот'.split()))
RU_MONTHS = 'января февраля марта апреля мая июня июля августа сентября октября ноября декабря'.split()
RU_ABBREVIATIONS = {'млн': 'миллионов', 'млрд': 'миллиардов', 'трлн': 'триллионов', 'тыс': 'тысяч'}
RU_FRACTIONS = {1: 'десятых', 2: 'сотых', 3: 'тысячных'}


def plural(n, forms):
    """Russian agreement: 1 процент, 2 процента, 5 процентов."""
    if n % 10 == 1 and n % 100 != 11:
        return forms[0]
    return forms[1] if n % 10 in (2, 3, 4) and n % 100 not in (12, 13, 14) else forms[2]


def cardinal_ru(n):
    for scale, forms in RU_SCALES:
        if n >= scale:
            head, rest = n // scale, n % scale
            words = [] if head == 1 and scale == 1000 else cardinal_ru(head)   # "тысяча девятьсот"
            if scale == 1000 and words and words[-1] in ('один', 'два'):
                words[-1] = 'одна' if words[-1] == 'один' else 'две'
            return words + [plural(head, forms)] + (cardinal_ru(rest) if rest else [])
    if n >= 100:
        return [RU_HUNDREDS[n // 100]] + (cardinal_ru(n % 100) if n % 100 else [])
    if n >= 20:
        return [RU_TENS[n // 10]] + ([RU_ONES[n % 10]] if n % 10 else [])
    return [RU_ONES[n]]


def ordinal_ru(words, following):
    """Last word as an ordinal in the case the next word asks for: 2024 года, в 2024 году, 5 мая, XX век."""
    stem = RU_ORDINALS.get(words[-1])
    case = 'nominative' if following in ('год', 'век') else 'prepositional' if following in ('году', 'веке') else \
        'genitive' if following in ('года', 'века') or following in RU_MONTHS else None
    if not stem or not case:
        return words
    base = stem.rstrip('*~')
    if stem.endswith('~'):
        ending = {'nominative': 'ий', 'genitive': 'ьего', 'prepositional': 'ьем'}[case]
    else:
        ending = {'nominative': 'ой' if stem.endswith('*') else 'ый', 'genitive': 'ого', 'prepositional': 'ом'}[case]
    return words[:-1] + [base + ending]


def ordinal(words):
    return words[:-1] + [words[-1] + ('nchi' if words[-1][-1] in 'ai' else 'inchi')]


def roman(match):
    letters, total = match.group(), 0
    for k, letter in enumerate(letters):
        value = ROMAN_VALUES[letter]
        total += -value if k + 1 < len(letters) and ROMAN_VALUES[letters[k + 1]] > value else value
    return ' '.join(ordinal(cardinal(total)))


def roman_value(match):
    letters, total = match.group(), 0
    for k, letter in enumerate(letters):
        value = ROMAN_VALUES[letter]
        total += -value if k + 1 < len(letters) and ROMAN_VALUES[letters[k + 1]] > value else value
    return str(total)


def written_numbers(text, language='uz'):
    """Roman numerals, digit groups, decimals and per cent as they are read aloud."""
    if language == 'ru':
        text = RU_ROMAN_RE.sub(roman_value, text)   # "XX век" -> "20 век" -> "двадцатый век"
        text = GROUPED.sub(lambda m: re.sub(r'\D', '', m.group()), text)
        text = PERCENT.sub(lambda m: '%s%s %s ' % (m.group(1), m.group(2) or '', 'процента' if m.group(2) else plural(
            int(m.group(1)), ('процент', 'процента', 'процентов'))), text)
        return DECIMAL.sub(lambda m: '%s целых %d %s' % (m.group(1), int(m.group(2)), RU_FRACTIONS[len(m.group(2))]), text)
    text = ROMAN_RE.sub(roman, text)
    text = GROUPED.sub(lambda m: re.sub(r'\D', '', m.group()), text)
    text = DECIMAL.sub(lambda m: '%s butun %s %d' % (m.group(1), FRACTIONS[len(m.group(2))], int(m.group(2))), text)
    return text.replace('%', ' foiz ')


def normalize(text):
    text = unicodedata.normalize('NFKC', text.replace('№', ' ')).lower()
    text = re.sub(r'(?<!\w)е', 'ye', text)  # word-initial е is written "ye" in Uzbek Latin
    text = ''.join(CYRILLIC.get(ch, ch) for ch in text)
    for mark in APOSTROPHES:
        text = text.replace(mark, "'")
    return text


def cardinal(n):
    if n < 10:
        return [UNITS[n]]
    if n < 100:
        return [TENS[n // 10]] + (cardinal(n % 10) if n % 10 else [])
    if n < 1000:
        return cardinal(n // 100) + ['yuz'] + (cardinal(n % 100) if n % 100 else [])
    if n < 1000000:
        return cardinal(n // 1000) + ['ming'] + (cardinal(n % 1000) if n % 1000 else [])
    if n < 1000000000:
        return cardinal(n // 1000000) + ['million'] + (cardinal(n % 1000000) if n % 1000000 else [])
    return cardinal(n // 1000000000) + ['milliard'] + (cardinal(n % 1000000000) if n % 1000000000 else [])


RU_ROMAN_RE = re.compile(r'\b(?=[IVX]{2,}\b)X{0,3}(?:IX|IV|V?I{0,3})\b|\b[IVX]\b(?=\s+век)')
# Number words are produced in Cyrillic and compared in the same Latin form as everything else.
RU_FOLLOWING = {normalize(w): w for w in ['год', 'года', 'году', 'век', 'века', 'веке'] + RU_MONTHS}
RU_SHORT = {normalize(k): normalize(v) for k, v in RU_ABBREVIATIONS.items()}


def spoken_numbers(values, language, following=''):
    """Expand digits to the words they are read with. `following` is the word after the last value."""
    output, links = [], []
    for i, value in enumerate(values):
        parts = [value]
        after = values[i + 1] if i + 1 < len(values) else following
        digits = value.isascii() and value.isdigit() and len(value) <= 12
        if language == 'uz' and value in ABBREVIATIONS:
            parts = [ABBREVIATIONS[value]]
        elif language == 'uz' and digits:
            parts = cardinal(int(value))
            if after.startswith(('yil', 'son', 'sinf', 'asr', 'kurs', 'o\'rin')):
                parts = ordinal(parts)
        elif language == 'ru' and value in RU_SHORT:
            parts = [RU_SHORT[value]]
        elif language == 'ru' and digits:
            parts = [normalize(w) for w in ordinal_ru(cardinal_ru(int(value)), RU_FOLLOWING.get(after, ''))]
        output.extend(parts)
        links.extend([i] * len(parts))
    return output, links


def tokens(text, language='uz', following=''):
    """Comparable tokens of a text. `language=None` only normalises; `following` is the text after it."""
    if language in ('uz', 'ru'):
        text = written_numbers(text, language)
    after = TOKEN.findall(normalize(following))
    return spoken_numbers(TOKEN.findall(normalize(text)), language, after[0] if after else '')[0]


def marked_tokens(text, language='uz'):
    """Tokens with the punctuation that follows each: 'P' paragraph, '.' sentence, ',' clause, '' none."""
    if language in ('uz', 'ru'):
        text = written_numbers(text, language)
    text = normalize(text)
    matches = list(TOKEN.finditer(text))
    raw, marks = [], []
    for i, match in enumerate(matches):
        tail = text[match.end():matches[i + 1].start() if i + 1 < len(matches) else len(text)]
        if '\n' in tail or i + 1 == len(matches):
            mark = 'P'
        elif re.search(r'[.!?…]', tail):
            mark = '.'
        elif re.search(r'[,;:—–]|\s-\s', tail):
            mark = ','
        else:
            mark = ''
        raw.append(match.group())
        marks.append(mark)
    values, links = spoken_numbers(raw, language)
    # Punctuation belongs to the last spoken part of an expanded number.
    result = []
    for k, link in enumerate(links):
        last = k + 1 == len(links) or links[k + 1] != link
        result.append((values[k], marks[link] if last else ''))
    return result


def detect_language(text):
    letters = re.findall(r'[^\W\d_]', text.lower())
    if not letters:
        return 'uz'
    cyrillic = sum('а' <= ch <= 'я' or ch in 'ёўқғҳ' for ch in letters)
    uzbek = sum(ch in 'ўқғҳ' for ch in letters)
    russian = sum(ch in 'ыщэ' for ch in letters)
    if cyrillic / len(letters) > .5 and russian > uzbek * 2 and russian / len(letters) > .004:
        return 'ru'
    return 'uz'
