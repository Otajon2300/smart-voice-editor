import unittest

from helpers import docx, docx_body
from text import tokens, marked_tokens, detect_language
from script import paragraphs, parse_script, tokenize

RUSSIAN = ['ТВ эфир на рус.яз. от 01.11.26г. в 19.30ч.', 'Репортаж на тему: «Школа»', 'Стендап',
           '- Являясь образцом высокого профессионализма искусство бахши пользуется почетом.',
           'Кашкадарьинская область', 'Чиракчинский район',
           'Корреспондент – Фольклорный фестиваль превратился в масштабный праздник для людей.',
           'СНХР: Мансур Эшкувватов /Камашинский район/ на узб.яз.',
           '- Мы из школы музыки и искусства и приехали сюда почтить память бахши.',
           'Корреспондент - Традиции эпоса всегда передавались от отца к сыну.',
           'Звук песни',
           'Корреспондент – Согласно дорожной карте появились специальные классы.',
           'Стендап', '- Узбекистан обретает известность как страна подлинно музыкальная.']


class TextTests(unittest.TestCase):
    def test_cyrillic_and_latin_match(self):
        self.assertEqual(tokens('Ўзбекистон ғалаба қилди'), tokens("O‘zbekiston g'alaba qildi"))
        self.assertEqual(tokens('ердамида'), ['yerdamida'])

    def test_uzbek_numbers_are_spoken(self):
        self.assertEqual(tokens('2024-yilda 15 ta'), ['ikki', 'ming', 'yigirma', "to'rtinchi", 'yilda', "o'n", 'besh', 'ta'])
        self.assertEqual(tokens('XXI asr'), ['yigirma', 'birinchi', 'asr'])
        self.assertEqual(tokens('Vitamin C va X'), ['vitamin', 'c', 'va', 'x'])  # lone letters stay letters

    def test_numbers_as_they_are_read(self):
        self.assertEqual(tokens("1 500 000 so'm"), ['bir', 'million', 'besh', 'yuz', 'ming', "so'm"])
        self.assertEqual(tokens('1.500.000'), ['bir', 'million', 'besh', 'yuz', 'ming'])
        self.assertEqual(tokens('3,5 foiz'), ['uch', 'butun', "o'ndan", 'besh', 'foiz'])
        self.assertEqual(tokens('0,25'), ['nol', 'butun', 'yuzdan', 'yigirma', 'besh'])
        self.assertEqual(tokens('25%'), ['yigirma', 'besh', 'foiz'])
        self.assertEqual(tokens('1,2 mlrd'), ['bir', 'butun', "o'ndan", 'ikki', 'milliard'])
        self.assertEqual(tokens('5 млн'), ['besh', 'million'])
        self.assertEqual(tokens('2024 150 kishi')[:4], ['ikki', 'ming', 'yigirma', "to'rt"])  # not one number
        self.assertEqual([m for _, m in marked_tokens('Narx 3,5 foiz, keyin')], ['', '', '', '', '', ',', 'P'])

    def test_roman_numerals(self):
        self.assertEqual(tokens('XIX asr'), ["o'n", "to'qqizinchi", 'asr'])
        self.assertEqual(tokens('XV asrda'), ["o'n", 'beshinchi', 'asrda'])
        self.assertEqual(tokens('II bosqich'), ['ikkinchi', 'bosqich'])
        self.assertEqual(tokens('XX asr'), ['yigirmanchi', 'asr'])
        self.assertEqual(tokens('V asr'), ['beshinchi', 'asr'])
        self.assertEqual(tokens('MIX va XL'), ['mix', 'va', 'xl'])

    def test_russian_numbers_as_they_are_read(self):
        def ru(text, following=''):
            return ' '.join(tokens(text, 'ru', following))
        same = lambda text: ' '.join(tokens(text, 'ru'))
        self.assertEqual(ru('школы №26'), same('школы двадцать шесть'))
        self.assertEqual(ru('В 2024 году'), same('в две тысячи двадцать четвертом году'))
        self.assertEqual(ru('5 мая 1999 года'), same('пятого мая тысяча девятьсот девяносто девятого года'))
        self.assertEqual(ru('XX век, в XIX веке'), same('двадцатый век в девятнадцатом веке'))
        self.assertEqual(ru('3 места и 2 года'), same('три места и второго года'))   # only год/век/months are ordinal
        self.assertEqual(ru('1 500 000 рублей'), same('один миллион пятьсот тысяч рублей'))
        self.assertEqual(ru('21 тыс. и 2 000'), same('двадцать один тысяч и две тысячи'))
        self.assertEqual(ru('112, 40, 1000, 2001'), same('сто двенадцать сорок тысяча две тысячи один'))
        self.assertEqual(ru('21%, 3 % и 3,5%'), same('двадцать один процент три процента и три целых пять десятых процента'))
        self.assertEqual(ru('5 млн, 2,5 млрд'), same('пять миллионов два целых пять десятых миллиардов'))
        # The recogniser gives one word at a time: the next word still decides the reading.
        self.assertEqual(ru('2024', ' года'), same('две тысячи двадцать четвертого'))
        self.assertEqual(ru('2024'), same('две тысячи двадцать четыре'))
        self.assertEqual([m for _, m in marked_tokens('В 2024 году, да', 'ru')], ['', '', '', '', '', ',', 'P'])
        # No language: nothing is expanded.
        self.assertEqual(tokens('5 мая', None), ['5', 'maya'])

    def test_punctuation_marks(self):
        marks = [m for _, m in marked_tokens('Bir, ikki uch. To‘rt\nbesh')]
        self.assertEqual(marks, [',', '', '.', 'P', 'P'])

    def test_language(self):
        self.assertEqual(detect_language('Мы из школы музыки и приехали сюда почтить память.'), 'ru')
        self.assertEqual(detect_language('Тасаввур қилинг бепоён дашт.'), 'uz')


class UzbekLabelTests(unittest.TestCase):
    def test_interview_marks_without_a_delimiter(self):
        blocks = parse_script(docx([
            'ДИКТОР: Биринчи даъво шундай эди ва у кўп тарқалган.',
            'INT ALIYEV VALI',
            'ДИКТОР: Бу даъвонинг тарихий қиймати катта.',
            'Int Aliyev Vali',
            'ВИЗУАЛ/КАДР: «Муҳр босилиши» бренд анимацияси бошланади.',
            'ДИКТОР: БОШЛОВЧИ (камера олдида): Бугун биз бутун бир дунёни кўрдик.',
            'INTERVIYU ALIYEV VALI',
            'ДИКТОР: Интернет тармоғида бу хабар тез тарқалди.',
            'Intervyu davomida u shunday dedi.',
        ]))
        kinds = [b['kind'] for b in blocks]
        self.assertEqual(kinds, ['narration', 'sync', 'narration', 'sync', 'note', 'narration', 'sync', 'narration'])
        self.assertEqual([b['label'] for b in blocks if b['kind'] == 'sync'], ['ALIYEV VALI', 'Aliyev Vali', 'ALIYEV VALI'])
        self.assertEqual(blocks[5]['text'], 'Бугун биз бутун бир дунёни кўрдик.')         # neither the label nor the remark is read
        self.assertIn('Intervyu davomida', blocks[7]['text'])                              # an ordinary sentence stays text
        self.assertFalse(any('Муҳр' in b['text'] for b in blocks))


class ScriptTests(unittest.TestCase):
    def test_russian_report_parts(self):
        blocks = parse_script(docx(RUSSIAN))
        self.assertEqual([b['kind'] for b in blocks], ['header', 'header', 'standup', 'caption', 'caption', 'narration',
                                                      'sync', 'narration', 'sound', 'narration', 'standup'])
        self.assertIn('Мансур', blocks[6]['label'])
        self.assertIn('Мы из школы', blocks[6]['text'])
        script, marks, owner = tokenize(blocks, 'ru')
        self.assertEqual(len(script), len(marks))
        self.assertEqual(owner[0], 2)

    def test_uzbek_headings(self):
        blocks = parse_script(docx(['«СИРЛИ САҲИФА»', 'КИРИШ — HOOK (00:00–01:53)', 'ДИКТОР: Тасаввур қилинг бепоён дашт.',
                                    '1-АКТ — БАЛБАЛ НИМА (01:53–09:39)', 'ДИКТОР: Аввал энг оддий саволдан бошлаймиз.']))
        self.assertEqual([b['kind'] for b in blocks], ['header', 'header', 'narration', 'heading', 'narration'])

    def test_ordinary_sentence_is_not_a_label(self):
        blocks = parse_script(docx(['ДИКТОР: Салом.', 'Овоз бериш жараёни бугун бошланди ва давом этмоқда.']))
        self.assertEqual([b['kind'] for b in blocks], ['narration'])

    def test_breaks_and_tabs_separate_words(self):
        body = '<w:p><w:r><w:t>salom</w:t><w:br/><w:t>dunyo</w:t><w:tab/><w:t>yana</w:t><w:cr/><w:t>bir</w:t></w:r></w:p>'
        self.assertEqual(paragraphs(docx_body(body)), ['salom dunyo yana bir'])
        self.assertEqual(tokenize(parse_script(docx_body(body)), 'uz')[0], ['salom', 'dunyo', 'yana', 'bir'])

    def test_line_breaks_inside_one_paragraph_are_script_lines(self):
        # Text pasted from a messenger: the whole script is one Word paragraph with Shift+Enter breaks.
        lines = ['"Jarayon"', '', 'Muxbir: Hudud taraqqiyoti boshqaruv tizimida namoyon bo‘ladi. Bu tajriba muhim.', '',
                 'Intervyu: Mahmud Qodirov — Xalq deputatlari Beruniy tumani Kengashi kotibi', '',
                 'Muxbir: Hududni rivojlantirishda loyihalar muhim.',
                 '[19.11.2026 11:45] ShoMuRoDov: Delegatsiya vakillari tajribalarni o‘rgandilar.', '',
                 'INTERVYU: Xalilla Eshimbetov — deputat', '', 'Koson tumani kadrlari',
                 'Muxbir: Uch kunlik tashrif yakunlandi.', '', 'Muxbir: X. Shomurodov', 'Tasvirchi: J. Sultonov',
                 'Montaj: A. Ro‘ziboyev']
        body = '<w:p><w:r>%s</w:r></w:p>' % '<w:br/>'.join('<w:t>%s</w:t>' % line for line in lines)
        blocks = parse_script(docx_body(body))
        self.assertEqual([b['kind'] for b in blocks],
                         ['header', 'narration', 'sync', 'narration', 'sync', 'note', 'narration', 'note', 'note', 'note'])
        self.assertEqual(blocks[2]['label'], 'Mahmud Qodirov — Xalq deputatlari Beruniy tumani Kengashi kotibi')
        self.assertEqual(blocks[2]['text'], '')
        self.assertNotIn('ShoMuRoDov', blocks[3]['text'])
        self.assertIn('Delegatsiya vakillari', blocks[3]['text'])

    def test_tracked_deletions_and_field_codes_are_not_script(self):
        body = ('<w:p><w:r><w:t xml:space="preserve">bugun </w:t></w:r>'
                '<w:del><w:r><w:delText>eski matn</w:delText></w:r></w:del>'
                '<w:moveFrom><w:r><w:t>ko‘chirilgan</w:t></w:r></w:moveFrom>'
                '<w:ins><w:r><w:t xml:space="preserve">yangi </w:t></w:r></w:ins>'
                '<w:r><w:instrText>PAGE</w:instrText></w:r><w:r><w:t>matn</w:t></w:r></w:p>')
        self.assertEqual(paragraphs(docx_body(body)), ['bugun yangi matn'])

    def test_text_box_is_read_once(self):
        box = '<w:txbxContent><w:p><w:r><w:t>ramka ichida</w:t></w:r></w:p></w:txbxContent>'
        body = ('<w:p><w:r><w:t>oldin</w:t></w:r><w:r><mc:AlternateContent><mc:Choice>%s</mc:Choice>'
                '<mc:Fallback>%s</mc:Fallback></mc:AlternateContent></w:r><w:r><w:t>keyin</w:t></w:r></w:p>' % (box, box))
        self.assertEqual(paragraphs(docx_body(body)), ['oldinkeyin', 'ramka ichida'])

    def test_non_breaking_hyphen_separates_words(self):
        body = '<w:p><w:r><w:t>2024</w:t><w:noBreakHyphen/><w:t>yil</w:t><w:softHyphen/><w:t>da</w:t></w:r></w:p>'
        self.assertEqual(paragraphs(docx_body(body)), ['2024-yilda'])
        self.assertEqual(tokenize(parse_script(docx_body(body)), 'uz')[0][-2:], ["to'rtinchi", 'yilda'])

    def test_plain_text_script(self):
        import os
        import tempfile
        for encoding in ('utf-8-sig', 'cp1251', 'utf-16'):
            handle = tempfile.NamedTemporaryFile(suffix='.txt', delete=False)
            handle.write('Диктор: Тасаввур қилинг.\r\n\r\nСНХР: Али Валиев\r\n- Жуда яхши.\r\n'.replace('қ', 'к' if encoding == 'cp1251' else 'қ')
                         .encode(encoding))
            handle.close()
            try:
                self.assertEqual([b['kind'] for b in parse_script(handle.name)], ['narration', 'sync'], encoding)
            finally:
                try:
                    os.unlink(handle.name)
                except OSError:
                    pass

    def test_bad_file(self):
        with self.assertRaises(ValueError):
            parse_script('missing.docx')
        with self.assertRaises(ValueError):
            parse_script('missing.txt')
        with self.assertRaises(ValueError):
            parse_script('old.doc')


if __name__ == '__main__':
    unittest.main()
