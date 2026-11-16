# Smart Voice Editor — loyiha haqida umumiy hujjat

**Maqsadli muhit:** Adobe Premiere Pro 2020 va undan keyingi versiyalar (2019 dan yuqori)  
**Arxitektura:** CEP panel + Python backend  
**Asosiy til:** o‘zbekcha diktor nutqi  
**Suhbatda tilga olingan so‘nggi prototip:** v0.2  
**Hujjat sanasi:** 2026-yil 31-oktabr

> **Holat bo‘yicha eslatma:** bu hujjat loyiha haqidagi suhbatga asoslangan. Oldingi javoblarda prototip kodi va ZIP arxivlari tayyorlangani aytilgan, lekin ushbu hujjatni tayyorlashda o‘sha arxivlar yoki manba kodi tekshirilmagan. Quyidagi “prototipda borligi aytilgan” iborasi mustaqil tasdiqlangan, amalda sinalgan imkoniyatni anglatmaydi.

## Yangilangan asosiy talablar

**2026-10-31 — mahalliy v0.4 sinovi:** foydalanuvchi bergan 577.984 soniyalik M4A va Desktop’dagi 581 so‘zlik Word fayli tekshirildi. O‘zbekchaga moslashtirilgan Whisper Small modeli bilan transkripsiya CPU’da 93.74 soniya oldi. Yaqin yozilish, kirill-lotin, apostrof bo‘laklari va sonlar normallashtirilgach algoritmik moslik 97.79% chiqdi; bu inson baholagan aniqlik emas. Kesimlarni alohida ko‘rish, eshitish, belgilash va vaqtini tuzatish paneli qo‘shildi. Noaniq nutq saqlanadi; eski to‘liq aynan-moslik bloki asosiy oqimdan olib tashlandi. Timeline overwriteClip chaqirig‘idagi ticks/soniya xatosi tuzatildi. Haqiqiy Premiere UI sinovi boshqaruv vositasi xatosi tufayli yakunlanmagan; mock host va headless panel tekshirildi. Nafas pasaytirish, video va ko‘p klipli montaj hali yo‘q. Amaldagi imkoniyat va cheklovlar `README.md` da.

**2026-10-31 — yangi mahalliy v0.3 kodi boshlandi:** ushbu papkada `extension/`, `backend/`, testlar va ishga tushirish skriptlari yaratildi. Bu oldingi ZIP paketlar tiklangani degani emas. Hozirgi kod bitta oddiy audio klip uchun ssenariyga mos qismlar rejasini tuzish va zaxira nusxadan keyin ochiq sequence ichida qayta yig‘ishni amalga oshiradi. Python mantiqi, host himoyalari va HTTP so‘rovlari tekshirildi; Premiere ichidagi haqiqiy montaj hamda o‘zbekcha audio aniqligi hali sinalmagan. Nafas pasaytirish, video va ko‘p klipli montaj hali qo‘shilmagan. Amaldagi yo‘riqnoma: `README.md`.

Quyidagi talablar foydalanuvchining keyingi aniqlashtirishidir va hujjatdagi avvalgi rejalardan ustun turadi:

- Adobe Premiere Pro 2019 dan yuqori, ya’ni 2020 va undan keyingi versiyalar uchun ishlash mo‘ljallanadi. Har bir versiya bilan moslik alohida tekshirilishi kerak.
- Asosiy natija — ochiq sequence’ning o‘zida montaj: ssenariyga mos kelmaydigan urinishlar, takrorlar va ortiqcha pauzalar timeline’dagi kliplardan bevosita kesiladi.
- Alohida WAV yaratish asosiy natija bo‘lishi shart emas. Sequence ichida bevosita kesish keyingi ixtiyoriy bosqich emas, asosiy funksional talabdir.
- Asl media fayllari o‘zgartirilmaydi; kesishlar sequence’dagi kliplar va ularning vaqt chegaralariga tatbiq etiladi.

Bu talablar hali amalga oshirilgan imkoniyatlar sifatida tasdiqlanmagan. Quyidagi prototip tarixi va oldingi WAV ish oqimi avvalgi konseptni hujjatlashtiradi.

## 1. Loyiha nima uchun kerak?

Smart Voice Editor — Word ssenariysi asosida diktor yozuvini montaj qilishga yordam beradigan Premiere Pro kengaytmasi. Diktor o‘qish vaqtida adashishi, bir so‘z yoki gapni qayta aytishi, noto‘g‘ri variantdan keyin to‘g‘ri variantni o‘qishi mumkin. Loyihaning vazifasi — ssenariyga mos to‘g‘ri qismlarni saqlash, ortiqcha urinishlarni aniqlash va ularni tahrirlashni yengillashtirish.

Bu faqat sukunatni kesish vositasi emas. Asosiy ehtiyoj — **tayyor ssenariy bilan haqiqiy o‘qilgan nutqni solishtirish**. Nafas tovushlarini pasaytirish va uzun pauzalarni qisqartirish shu jarayonga qo‘shimcha ishlov sifatida qo‘shiladi.

### Kutiladigan natijaga misol

**Word ssenariysi:**

> Bugun mamlakatimizda yangi loyiha ishga tushirildi. Unda yuzlab yoshlar ishtirok etdi.

**Diktor yozuvi:**

> Bugun mamlakatimizda yangi... yangi loyiha boshlandi... yo‘q, ishga tushirildi. Unda yuzlab... yuzlab yoshlar ishtirok etdi.

**Maqsadli montaj:**

> Bugun mamlakatimizda yangi loyiha ishga tushirildi. Unda yuzlab yoshlar ishtirok etdi.

Bu misol funksional maqsadni ko‘rsatadi; aynan shu sifat prototipda olingani sinov bilan tasdiqlanmagan.

## 2. Kirish va chiqish ma’lumotlari

| Ma’lumot | Talab va hozirgi holat |
|---|---|
| Ssenariy | Word `.docx` fayli. Unda diktor o‘qishi kerak bo‘lgan tayyor matn bo‘ladi. |
| Alohida audio | WAV yoki MP3. Alohida audioni tahlil qilish kodi v0.1 tavsifida borligi aytilgan; formatlar bo‘yicha amaliy sinov natijalari berilmagan. |
| Timeline audiosi | Foydalanuvchi talab qilgan ikkinchi kirish usuli. Timeline bilan bevosita ishlash rejalashtirilgan. |
| Asosiy natija | Asl yozuvdan alohida yaratiladigan, tahrirlangan WAV fayli. |
| Premiere ichidagi natija | Natijani import qilish, timeline yoki alohida sequence’da joylashtirish va kesilgan kliplar bilan ishlash — keyingi bosqich. |

Audio ichida umuman o‘qilmagan so‘zni bu loyiha avtomatik yaratishi nazarda tutilmagan. Ssenariyning ayrim qismi yozuvda bo‘lmasa, uni qayta yozish yoki qo‘lda hal qilish kerak bo‘ladi.

## 3. Texnik tuzilma

### CEP panel

Premiere Pro 2020 uchun suhbatda CEP panel tanlangan. Panel foydalanuvchi bilan ishlash oynasi bo‘lib, ssenariy va audio tanlash, sozlamalarni berish hamda ishlov berishni boshlash uchun mo‘ljallangan. UXP bu loyihaning tanlangan asosiy arxitekturasi emas.

Panel mavjudligi prototip tavsifida aytilgan, biroq uning Premiere Pro 2020 ichida to‘liq ishlashi tekshirilmagan. Aniq o‘rnatish yo‘llari, operatsion tizimlar va bog‘liqliklar asl paket ko‘rilmasdan tasdiqlanmaydi.

### Python backend

Python qismi Word matnini o‘qish, audio tahlili, mos qismlarni tanlash va WAV natija yaratish uchun mo‘ljallangan. Nafas va pauzalarga ishlov berish ham shu tahlil jarayoniga kiradi.

Suhbatda nutqni tanish modeli, Python versiyasi, kutubxonalar, modelni yuklab olish tartibi, GPU talabi va panel bilan backend orasidagi aloqa protokoli aniq ko‘rsatilmagan. Shu sababli ular tayyor yechimning tasdiqlangan xususiyatlari sifatida berilmaydi.

### Maqsadli ma’lumot oqimi

```text
Word (.docx) ───────────────┐
                           ├─ Matn va nutqni solishtirish
WAV/MP3 → nutq tahlili ─────┘
                              ↓
                   Mos qismlarni tanlash
                              ↓
            Nafasni pasaytirish va pauzalarni qisqartirish
                              ↓
                       Alohida WAV natija
                              ↓
              Premiere timeline bilan integratsiya
                         (rejalashtirilgan)
```

Bu sxema mo‘ljallangan ish oqimini ifodalaydi; barcha bosqichlarning amaldagi bajarilish tartibi kod tekshiruvisiz tasdiqlanmaydi.

## 4. Funksiyalar va ularning holati

| Funksiya | Suhbat asosidagi holat | Cheklov |
|---|---|---|
| CEP panel va Python asos | v0.1 prototipida borligi aytilgan | Premiere ichida ishlashi tasdiqlanmagan |
| `.docx` matnini o‘qish | v0.1 kodida borligi aytilgan | Haqiqiy Word fayllari bilan natijalar berilmagan |
| Alohida audioni tahlil qilish | v0.1 kodida borligi aytilgan | O‘zbekcha nutqni tanish aniqligi o‘lchanmagan |
| Mos qismlardan WAV yaratish | v0.1 kodida borligi aytilgan | Montaj sifati va to‘liqligi tasdiqlanmagan |
| Xato o‘qish va takrorlarni aniqlash | Loyihaning asosiy maqsadi; dastlabki moslashtirish prototipi tavsiflangan | Ishonchli avtomatik aniqlash darajasi noma’lum |
| To‘g‘ri variantlarni saqlash | Maqsadli xatti-harakat | Eng yaxshi dublni tanlash sifati sinalmagan |
| Nafasni 75% pasaytirish | v0.2 da qo‘shilgani aytilgan | Detektor evristik; foizning signalga aniq tatbiqi tekshirilmagan |
| Uzun pauzalarni qisqartirish | v0.2 da yoqilgani aytilgan | Pauza chegarasi va yakuniy davomiylik ko‘rsatilmagan |
| Asl audioni saqlash | Prototip tavsifidagi ishlash tamoyili | Faylni qayta yozmaslik amalda tekshirilishi kerak |
| Timeline audiosini bevosita olish | Rejalashtirilgan | v0.1 da qo‘shilmagani aniq aytilgan; v0.2 da tasdiqlanmagan |
| Natijani timeline’ga qaytarish | Rejalashtirilgan | Avtomatik joylashtirish hali tasdiqlanmagan |
| So‘z darajasida aniq kesish | Keyingi rivojlantirish vazifasi | v0.1 da mavjud emasligi aytilgan |
| Shubhali kesimlarni ko‘rish va tiklash | Rejalashtirilgan | Tayyor tekshirish interfeysi tasdiqlanmagan |
| Maxsus AI nafas modeli | Kelajakdagi takomillashtirish imkoniyati | Hozirgi nafas detektori to‘liq AI modeli emas |

## 5. Ssenariyga moslashtirish

Maqsadli jarayonda audio matnga aylantiriladi va Word ssenariysi bilan solishtiriladi. Dastur takrorlar, tugallanmagan urinishlar va noto‘g‘ri aytilgan bo‘laklar orasidan ssenariyga mos qismlarni topishi kerak.

Quyidagi vaziyatlar alohida e’tibor talab qiladi:

- Bitta gapning bir necha marta, turli xatolar bilan o‘qilishi.
- Gapning faqat bir qismi qayta o‘qilishi.
- Ssenariyda bor so‘zning audioda yo‘qligi.
- Son, sana, qisqartma va atoqli otlarning yozilishi bilan talaffuzi farq qilishi.
- O‘zbekcha apostrof belgilarining turli ko‘rinishlari va lotin-kirill yozuvi farqlari.
- Matnga mos, lekin ohangi yoki talaffuzi sust bo‘lgan dubl.

Matn mosligi audio ijroning eng sifatli ekanini o‘z-o‘zidan bildirmaydi. Shuning uchun yakuniy tanlovni eshitib tekshirish muhim. Yozuvni normallashtirish, mazmuniy solishtirish va ishonch bahosi kabi usullar foydali rivojlantirish yo‘nalishlari bo‘lishi mumkin, lekin ularning prototipda borligi tasdiqlanmagan.

## 6. AI Breath Removal: kelishilgan sozlamalar

| Sozlama | Talab |
|---|---|
| Funksiya nomi | AI Breath Removal |
| Kuch | 75% |
| Rejim | Nafas tovushini pasaytirish |
| Butunlay o‘chirish | Tanlanmagan |
| Uzun pauzalar | Qisqartirilsin |
| Tabiiylik | Nutq va tabiiy nafas hissi saqlanishi kerak |

**“75%” nafaslarning 75 foizini topish yoki audioning 75 foizini kesish degani emas.** Bu foydalanuvchi tanlagan pasaytirish kuchidir. Uning amplituda, quvvat yoki boshqa shkala bo‘yicha hisoblanishi suhbatda aniqlashtirilmagan. Shu bois unga aniq dB qiymatini tenglashtirish mumkin emas.

v0.2 tavsifiga ko‘ra, hozirgi algoritm nutq orasidagi shovqinga o‘xshash tovushlarni tahlil qiladi. Bu maxsus o‘qitilgan nafasni aniqlash AI modeli sifatida tasdiqlanmagan. “AI Breath Removal” funksional nom bo‘lib, hozirgi texnologiyaning yetuklik darajasiga kafolat bermaydi.

Kutiladigan xatolar:

- Ayrim qisqa yoki juda past nafaslar aniqlanmay qolishi mumkin.
- Nafasga o‘xshash boshqa tovushlar ham pasayishi mumkin.
- Nutqqa yaqin nafaslarni qayta ishlash so‘z boshlanishi yoki oxiriga ta’sir qilishi mumkin.

Qisqa fade’lar yordamida silliq ulash va so‘z chegaralarini himoya qilish avvalgi konseptda tilga olingan. Ularning amaldagi bajarilishi va samarasi tekshirilmagan.

## 7. Uzun pauzalarni qisqartirish

Bu sozlama diktor o‘qishidagi ortiqcha kutishlarni kamaytirishga xizmat qiladi. Har bir pauzani yo‘qotish maqsad qilinmaydi: gaplar orasidagi tabiiy ritm va ma’no saqlanishi kerak.

v0.2 da uzun pauzalarni qisqartirish yoqilgani aytilgan. Biroq “uzun” pauzaning minimal davomiyligi, qisqartirilgandan keyin qoldiriladigan vaqt, sukunat chegarasi va nafas bilan ustma-ust kelgan pauzalarga ishlov berish tartibi ko‘rsatilmagan. Bu parametrlar kodni ko‘rish va real audio bilan tekshirish orqali aniqlashtirilishi kerak.

## 8. Asl yozuvni saqlash va WAV natija

Loyihaning kelishilgan tamoyili — **asl audio faylni o‘zgartirmasdan, alohida WAV natija yaratish**. Shu ma’noda jarayon non-destructive hisoblanadi: dastlabki yozuvga qaytish mumkin bo‘lishi kerak.

Biroq yakuniy WAV ichidagi kesilgan qismlarni uning o‘zidan tiklab bo‘lmaydi. Buning uchun asl audio saqlanishi zarur. Har bir kesimni alohida bekor qilish, manba vaqtiga qaytish yoki timeline’da qayta ochish uchun qo‘shimcha tahrir ma’lumotlari kerak; bunday jurnal yoki loyiha formati mavjudligi tasdiqlanmagan.

Chiqish WAV faylining namuna olish chastotasi, bit chuqurligi, kanal soni va balandlikni saqlash qoidalari suhbatda berilmagan. Ularni tayyor mahsulot xususiyati sifatida taxmin qilish kerak emas.

## 9. Premiere Pro bilan integratsiya

Foydalanuvchi ikkala usulni ham so‘ragan: kompyuterdagi WAV/MP3 bilan va Premiere timeline’dagi audio bilan ishlash.

Dastlabki prototip tavsifi alohida faylga ishlov berishga tegishli. Timeline’dan audio olish, tanlangan kliplar chegaralarini hisobga olish, natijani qaytarish va kesilgan bo‘laklarni alohida joylashtirish keyingi bosqich vazifalaridir. Alohida sequence’da natija tayyorlash ham suhbatda xavfsizroq ish usuli sifatida taklif qilingan, lekin tayyor imkoniyat sifatida tasdiqlanmagan.

Pauza va xato bo‘laklar kesilganda natijaning davomiyligi o‘zgaradi. Shu sababli video bilan sinxronlik, boshqa treklar va timeline joylashuvi integratsiya bosqichida alohida tekshirilishi lozim.

## 10. Prototiplar tarixi

### v0.1 — dastlabki prototip

Suhbatdagi javobda CEP panel, Python dasturi va o‘rnatish yo‘riqnomasi tayyorlangani aytilgan. Word faylini o‘qish, alohida audioni tahlil qilish va mos qismlardan WAV yaratish kodi borligi bildirilgan.

O‘sha tavsifning o‘zida dastur hali sinalmagani, timeline bilan to‘g‘ridan-to‘g‘ri ishlash va so‘z darajasida aniq montaj qo‘shilmagani qayd etilgan.

### v0.2 — nafas va pauza ishlovi

Keyingi javobda 75% kuch bilan nafasni pasaytirish hamda uzun pauzalarni qisqartirish qo‘shilgani aytilgan. Asl audio saqlanishi va natija WAV bo‘lishi ko‘rsatilgan.

Sintaktik tekshiruv va ZIP arxiv tekshiruvi muvaffaqiyatli o‘tgani bildirilgan. Shu bilan birga, Premiere Pro 2020 ichida haqiqiy audio bilan sinov hali o‘tkazilmagani ochiq aytilgan.

Avvalgi xabarlardagi ZIP nomlari: `smart_voice_editor_prototype.zip` va `smart_voice_editor_v02.zip`. Ular bu hujjat tarkibiga kiritilmagan; ushbu Markdown fayli dastur yoki o‘rnatish paketi emas.

## 11. Sinov cheklovlari

Sintaktik tekshiruv kodning yozilishida ayrim xatolar yo‘qligini ko‘rsatishi mumkin. ZIP tekshiruvi esa arxiv tuzilmasi bilan bog‘liq tekshiruvdir. Ularning hech biri quyidagilarni tasdiqlamaydi:

- Panelning Premiere Pro 2020 da ochilishi va backend bilan ishlashi.
- O‘zbekcha nutqni yetarli aniqlikda tanish.
- Takror va xato o‘qishlarni to‘g‘ri ajratish.
- Barcha kerakli iboralarning saqlanishi va kerakli tartibda ulanishi.
- Nafaslarni tabiiy eshitiladigan tarzda pasaytirish.
- So‘zlarning boshlanishi va oxiri shikastlanmasligi.
- MP3 dekodlash va WAV eksportining turli fayllarda ishlashi.
- Uzoq yozuvlarda tezlik, xotira sarfi va barqarorlik.
- Timeline sinxronligi va avtomatik import.

Suhbatda aniqlik foizi, ishlov berish tezligi yoki qo‘llab-quvvatlanadigan audio davomiyligi bo‘yicha o‘lchangan natijalar berilmagan. Loyihani hozircha ishlab chiqarishga tayyor mahsulot sifatida ta’riflash uchun asos yetarli emas.

## 12. Tavsiya etiladigan dastlabki sinov

Suhbatda keyingi qadam sifatida **1–2 daqiqalik haqiqiy WAV yoki MP3 yozuv va unga mos Word ssenariysi** bilan tekshirish taklif qilingan.

1. Asl audio va ssenariyni alohida saqlash.
2. Yozuvdagi xato o‘qishlar, takrorlar, nafaslar va uzun pauzalarni qo‘lda belgilash.
3. Prototipni 75% nafas pasaytirish va pauzalarni qisqartirish sozlamalari bilan ishlatish.
4. Natijani ssenariy bilan solishtirish va boshidan oxirigacha eshitish.
5. Kerakli nutq yo‘qolgan yoki noto‘g‘ri tanlangan joylarni qayd etish.
6. Nafas pasayishi, tabiiy ritm, kesimlar va shiqillash kabi artefaktlarni baholash.
7. Asl fayl o‘zgarmaganini va alohida WAV yaratilganini tekshirish.
8. Keyin turli diktor, shovqin darajasi va uzunroq yozuvlar bilan sinovni kengaytirish.

### Qabul qilish mezonlari uchun taklif

| Tekshiruv | Kutiladigan natija |
|---|---|
| Matn to‘liqligi | Asl yozuvda mavjud kerakli iboralar yo‘qolmaydi; mavjud bo‘lmagan iboralar yashirilmaydi |
| Takrorlar | Belgilangan takrorlar to‘g‘ri tanlanadi, kerakli dubl saqlanadi |
| Kesim sifati | So‘z va bo‘g‘inlar uzilmaydi, ulanishlar eshitib tekshiriladi |
| Nafas ishlovi | Nafas pasayadi; nutq va tabiiylik saqlanadi |
| Pauzalar | Ortiqcha kutish kamayadi; gaplar bir-biriga yopishib ketmaydi |
| Fayl xavfsizligi | Asl yozuv saqlanadi va alohida natija yaratiladi |
| Premiere bilan ishlash | Panel, natijani ochish va keyinchalik timeline integratsiyasi alohida sinaladi |

Bu mezonlar tavsiya hisoblanadi; ularning bajarilgani haqida hozircha sinov dalili yo‘q.

## 13. Keyingi rivojlantirish yo‘nalishlari

1. **Mavjud paketni tekshirish:** kod, bog‘liqliklar, o‘rnatish yo‘riqnomasi va real sozlamalarni aniqlash.
2. **Haqiqiy namunada baholash:** ssenariyga moslashtirish va nafas ishlovi xatolarini o‘lchash.
3. **Montaj aniqligini oshirish:** vaqt belgilarini yaxshilash, so‘z chegaralarini himoyalash va silliq ulash.
4. **Qo‘lda tekshirish imkoniyati:** shubhali kesimni eshitish, qabul qilish yoki tiklash.
5. **Timeline integratsiyasi:** audio olish, natijani qaytarish va alohida sequence yoki kliplar bilan ishlash.
6. **Nafas detektorini takomillashtirish:** kerak bo‘lsa maxsus model bilan taqqoslash va turli diktorlarda baholash.
7. **Barqarorlik va tarqatish:** xatolarni tushunarli ko‘rsatish, uzun fayllar bilan sinash va takrorlanadigan o‘rnatish jarayoni.

Bu ro‘yxat tavsiya etiladigan ish ketma-ketligi bo‘lib, yetkazib berish sanalari yoki bajarilgan ishlar ro‘yxati emas.

## 14. Ochiq texnik savollar

- Qaysi nutqni tanish modeli ishlatilgan va u o‘zbek tilida qanday natija beradi?
- Backend mahalliy ishlaydimi yoki tashqi xizmatga audio yuboradimi? Internet talabi va ma’lumot uzatish tartibi hali tasdiqlanmagan.
- “75%” sozlamasi signalga qanday formula bilan qo‘llanadi?
- Uzun pauza chegarasi va qoldiriladigan pauza qancha?
- Qaysi operatsion tizim, Python va kutubxona versiyalari sinalgan?
- Natijaning audio parametrlari qanday saqlanadi?
- Ssenariyda bor, lekin audioda yo‘q joy foydalanuvchiga qanday ko‘rsatiladi?
- Timeline’da tanlov, bir nechta klip, kanal va sinxronlik qanday boshqariladi?
- Kesimlar tarixi va manba vaqtlariga qaytish qanday ta’minlanadi?

## 15. Manba va hujjat chegarasi

Asosiy manba — [“Premiere Pro extension yozish” suhbatidagi loyiha tavsifi](chatgpt-conversation://6ae36d2c-ff38-83eb-b9d0-51287e7459cb) va ushbu hujjat uchun berilgan talablar.

Hujjat foydalanuvchi tanlagan talablarni, oldingi javoblarda bildirilgan prototip holatini va tavsiya etilgan keyingi ishlarni ajratib beradi. U manba kod auditi, o‘rnatish qo‘llanmasi yoki amaliy sinov hisoboti o‘rnini bosmaydi.
