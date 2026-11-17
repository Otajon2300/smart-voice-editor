# Smart Voice Editor 1.1.7

Premiere Pro uchun mahalliy CEP panel. Diktor yoki korrespondent ovozini Word ssenariysi bo‘yicha tozalaydi:
qayta o‘qishlar va tugallanmagan urinishlar kesiladi, ortiqcha pauzalar tabiiy uzunlikkacha qisqartiriladi, nafas ovozlari olib tashlanadi,
intervyu (СНХР/sinxron), stendap, ovoz va titr joylarida esa bo‘sh joy ochilib, unga matnli titr qo‘yiladi.

Premiere Pro **2017 (11.x, CEP 7)** dan boshlab keyingi CEP mavjud versiyalarga mo‘ljallangan.

## Ishlatish

1. Ishlab turgan istalgan sequence’da tozalanadigan ovozni **bitta audio trekda** tanlang: bitta klip yoki ketma-ket bir nechta klip.
   Video, musiqa, boshqa treklar va tanlanmagan kliplar o‘zgarmaydi. Audio klip videoga bog‘langan (linked) bo‘lsa, avval
   Unlink qiling: video joyida qoladi, faqat ovoz kesiladi va suriladi.
2. **1. Timeline’da tanlangan audio klip(lar)ni olish** ni bosing.
3. **Ssenariy tanlash** — bitta yoki bir nechta Word (`.docx`) yoki oddiy matn (`.txt`, UTF-8) fayli. Eski `.doc` ni Word’da
   `.docx` qilib saqlang. Bir yozuvda ikki reportaj o‘qilgan bo‘lsa, ikkala faylni tanlang: tartib audio bo‘yicha avtomatik aniqlanadi.
4. **3. Tahlil qilish**. Til (o‘zbek/rus) va model ssenariydan avtomatik tanlanadi. Uzoq tahlilni **Tahlilni bekor qilish**
   tugmasi bilan to‘xtatish mumkin.
5. Takliflarni, bo‘sh joylarni va pauzalarni ko‘rib chiqing. **▶ Natijani boshidan** — Premiere’da qanday bo‘lishini aniq eshitasiz;
   har bir taklif yonidagi **Asl** / **Natija** tugmalari shu joyni kesimgacha va kesimdan keyin eshittiradi.
   Belgini o‘zgartirsangiz reja darhol qayta hisoblanadi (tahlil qayta ishlamaydi).
   **Belgilangan kesimlarni tekshirdim** → **4. Sequence ichida tozalash**.

Natija shu sequence’ning o‘zida, tanlangan klip boshlangan joydan boshlab joylashadi. Asl media fayli o‘zgarmaydi.
Har bir amal `reports/` ga yoziladi.

**Orqaga qaytish.** Har bir bo‘lish, o‘chirish va surish Premiere’da alohida Undo qadami; yuzlab kesimda ular Undo tarixiga
sig‘masligi mumkin. Shuning uchun **Avval sequence’ning zaxira nusxasini saqlash** (sukut bo‘yicha yoqilgan) birinchi o‘zgarishdan
oldin loyihada `<sequence nomi> — zaxira SS.DD` nusxasini yaratadi. Xato bo‘lsa shu nusxani oching. Nusxa olinmasa, hech narsa
kesilmaydi.

### Tanilmagan tovush hech qachon jimgina kesilmaydi

Nutq tanish (ASR) ba’zan so‘z yoki butun gapni yozmay ketadi. Dastur bunday joyni “pauza” deb kesmaydi:

- ikki tanilgan so‘z orasida, yozuv boshida yoki oxirida 0.35 s dan ortiq **tanilmagan tovush** bo‘lsa, u saqlanadi va takliflar
  ro‘yxatida “Tanilmagan tovush (nutq bo‘lishi mumkin)” deb ko‘rsatiladi. Eshitib ko‘rib, keraksiz bo‘lsa belgilang;
- qisqa (0.06–0.3 s) tanilmagan tovushdan keyin pauza kelsa va ssenariyda shu joyda so‘z yo‘q bo‘lsa, bu duduqlanish bo‘lagi deb
  kesiladi, lekin ro‘yxatda “Tanilmagan qisqa tovush” bo‘lib turadi va belgini olib tashlash mumkin. Ssenariy shu joyda yana bir
  so‘z kutayotgan bo‘lsa (masalan ASR “va” ni yozmagan), tovush saqlanadi;
- “Uzun pauzalarni qisqartirish” o‘chirilgan bo‘lsa, yozuv boshi va oxiridagi sukunat ham kesilmaydi.

Uzluksiz nutq ichidan o‘tgan kesimlar ro‘yxatda **zich kesim** deb belgilanadi — ularni albatta eshiting.

**Nafas.** Kesilgan nafas o‘rnida kamida 0.2 s pauza qoladi: yonidagi toza sukunat yetmasa, qolgani bo‘sh (klipsiz) joy
bo‘lib ochiladi — titr ham, marker ham qo‘yilmaydi. 1.5–2 kHz atrofida shivirlaydigan sokin nafaslar ham aniqlanadi
(faqat ikki tomoni jim bo‘lsa — so‘z oxiridagi “х/с” ga tegmaslik uchun).

**Avtomatik qo‘llash.** “Tahlil tugagach o‘zi sequence’ga qo‘llasin” (sukut bo‘yicha yoqilgan) belgilangan bo‘lsa, 3-tugmadan
keyin natija darhol sequence’ga qo‘llanadi (zaxira nusxa bilan). Avval ko‘rib chiqmoqchi bo‘lsangiz belgini oling — ro‘yxatlar
yig‘ilgan holda turadi, sarlavhasini bosib oching, keyin 4-tugma. Yozuv ssenariyga mos kelmasa, avtomatik qo‘llanmaydi.

**Til.** Yozuv tilini foydalanuvchi tanlaydi: o‘zbekcha, ruscha yoki inglizcha (tanlov eslab qolinadi; dastur tilni o‘zi
taxmin qilmaydi). Inglizcha uchun ruscha bilan bir xil ko‘p tilli Whisper Medium ishlatiladi; inglizcha sonlar so‘zga
aylantirilmaydi (ssenariyda “2024”, o‘qilganda “twenty twenty-four” bo‘lsa, o‘sha joy mos kelmasligi mumkin).

**Titrlar.** Har bir titr uchun backend Premiere’ning “Basic Title” shablonidan nusxa yaratadi va matnni shablon faylining
o‘ziga yozadi (`.cache	itles	itr-….mogrt`, Arial 54), keyin Premiere uni import qiladi — Essential Graphics’da
tahrirlanadi. (Premiere o‘z grafikasining matnini skript orqali o‘zgartirishga ishonchli yo‘l bermaydi.) Loyiha papkasiga `titr.mogrt` qo‘ysangiz, o‘sha shablon ishlatiladi. Grafika qo‘yilmasa — avvalgidek rasm.

**Zaxira nusxa** endi sukut bo‘yicha o‘chirilgan (yangi sequence ochilmaydi); kerak bo‘lsa “Qo‘llash sozlamalari”da yoqing.

**Pauza ichidagi yolg‘iz tovush.** ASR yozmagan tovush ikki tomondan kamida 0.3 s jimlik bilan ajralgan va ssenariy shu
joyda uzilmasdan davom etgan bo‘lsa (yo‘tal, qog‘oz, chetga aytilgan so‘z), u ro‘yxatda ko‘rsatiladi va sukut bo‘yicha kesiladi.

**Intervyu belgilari.** Ssenariyda intervyu joyi ajratgichsiz ham taniladi: `INT Aliyev Vali`, `INTERVIYU …`,
`Intervyu: …`, `ИНТ …`, `Suhbat: …` (qisqa, nuqtasiz satr). `ВИЗУАЛ/КАДР: …` izoh sifatida o‘qilmaydi;
`ДИКТОР: БОШЛОВЧИ (камера олдида): …` da ikkinchi belgi va qavsdagi izoh matnga kirmaydi.

**Crossfade (ixtiyoriy, sukut bo‘yicha o‘chirilgan).** “Har bir kesimga 1 kadrlik crossfade” belgilansa, orasida bo‘sh joy
bo‘lmagan har bir ulanishga Premiere’ning Constant Power o‘tishi qo‘yiladi va “Natija” ham shunday eshittiriladi. Kesimlar
odatda sukunatga tushadi, shuning uchun bu asosan zich kesimlardagi “chiq” etgan tovush uchun kerak. O‘tish yarim kadr
davomida kesilgan qismning chetini ham eshittiradi. Premiere o‘tishni qo‘ya olmasa, ish to‘xtamaydi — xabarda nechta
ulanishga qo‘yilgani yoziladi.
Yozuv ssenariyga 50% dan kam mos kelsa (ehtimol boshqa fayl tanlangan), panel ogohlantiradi va hech bir taklif avtomatik belgilanmaydi.

### Ssenariy qanday o‘qiladi

| Ssenariyda | Dastur nima qiladi |
|---|---|
| `Корреспондент – …`, `ДИКТОР: …`, `Ведущий`, `Мухбир`, belgisiz davomi | Ovozda bo‘lishi kerak bo‘lgan matn; takror va pauzalar shu bo‘yicha tozalanadi |
| `СНХР:` / `Синхрон` / `Sinxron` + ism, keyingi `- …` matn | Intervyu. Tarjimasi ovozda o‘qilgan bo‘lsa saqlanadi; oldidan va keyin bo‘sh joy ochiladi. O‘qilmagan bo‘lsa matn uzunligiga qarab joy qoldiriladi |
| `Стендап` + matn | Kamerada yozilgan; ovozda yo‘q. Matn uzunligiga qarab bo‘sh joy (taxminan 2.4 so‘z/s) |
| `Звук …`, `Лайф`, `ЗТМ`, `Отбивка`, `«Сарлавҳа»` titr, `Кашкадарьинская область` kabi joy nomi | Bo‘sh joy va titr |
| `1-АКТ`, `01:53–03:39 — …` kabi sarlavhalar, hujjat boshidagi efir sanasi/mavzu | E’tiborga olinmaydi |

Har bir bo‘sh joyga bo‘sh video trekda titr (shaffof PNG, pastki tasmada СНХР/stendap matni) qo‘yiladi; klip nomi ham shu matn.
Sukut bo‘yicha titr **o‘chirilgan (disabled) klip** bo‘lib qo‘yiladi: timeline’da ko‘rinadi, lekin tasodifan eksportga chiqmaydi.
Ekranda ko‘rish kerak bo‘lsa “Titrlarni o‘chirilgan klip qilib qo‘yish” belgisini olib tashlang yoki klipni Enable qiling.
Sequence markeridan farqli, titr timeline’da ko‘rinadi va keyingi montajda klip sifatida suriladi. Rasmlar `.cache/titles` da,
loyihada **Smart Voice titrlar** papkasiga import qilinadi. Bo‘sh video trek bo‘lmasa yangi trek qo‘shiladi; bo‘lmasa marker qo‘yiladi.

Bo‘sh joy uzunligi panelda o‘zgartiriladi yoki o‘chiriladi. Qo‘shni matni o‘qilmagan bo‘sh joy “Joyi topilmadi” deb ko‘rsatiladi. Ovoz ssenariyning faqat bir qismi bo‘lsa (masalan, 10 daqiqa / 33 daqiqalik matn),
moslik faqat o‘qilgan qism bo‘yicha hisoblanadi.

### Pauzalar

Foydalanuvchi pauza uzunligini kiritmaydi. Har bir sukunat oldidagi so‘zga qarab qoldiriladi: bo‘lim oxiri ≈0.65 s, gap oxiri ≈0.5 s,
vergul ≈0.3 s, ibora ichida ≈0.2 s. Diktorning o‘qish tezligiga qarab qiymatlar ±15–20% moslashadi. Tabiiy pauza tegilmaydi.
Pauza ichidagi **nafas** (sukunatdan baland, nutqdan past, 2 kHz dan yuqori shovqinli 0.12–1 s tovush) kesiladi. Har ikki so‘z orasida
bitta kesim bo‘ladi: nafas ham, ortiqcha sukunat ham shu kesimga tushadi, qolgan pauza esa asl yozuvdagi **toza sukunat** (raqamli
“jimlik” qo‘shilmaydi). Toza sukunat kam bo‘lsa pauza biroz qisqaroq qoladi. Pauzalar ro‘yxatida istalgan pauzani o‘chirib, aslicha
qoldirish mumkin.

### Qayta o‘qishlar

O‘qish ssenariy bo‘ylab kuzatiladi. Diktor matnning oldingi joyiga qaytib qayta boshlasa, birinchi urinishdan qayta boshlangan joygacha
kesiladi; oxirgi variant saqlanadi (120 s gacha orqaga). Oxirgi variantda diktor 1–3 so‘zni o‘zgartirgan bo‘lsa ham oxirgi variant olinadi
va sabab ro‘yxatda ko‘rsatiladi. So‘z boshidagi duduqlanish (“yo- yoshlar”) va bitta so‘zning takrori ham kesiladi; ASR bitta so‘zni ikki
marta yozgan bo‘lsa (tovush uzluksiz), taklif belgilanmaydi va “tekshiring” deb ko‘rsatiladi.
60 s dan uzun yoki qayta o‘qilgan matn bilan kam mos keladigan kesimlar avtomatik belgilanmaydi — eshitib tasdiqlang.

Sonlar o‘qilgandek solishtiriladi: `1 500 000` → “bir million besh yuz ming”, `3,5` → “uch butun o‘ndan besh”, `25%` → “yigirma besh
foiz”, `mln/mlrd`, `2024-yil` → “…to‘rtinchi yil”, rim raqamlari II–XXXIX (`XIX asr` → “o‘n to‘qqizinchi asr”). Ruscha rejimda
ham sonlar so‘z bilan solishtiriladi: `2024 года` → “две тысячи двадцать четвёртого года”, `в 2024 году`, `5 мая`, `XX век`,
`21%` → “двадцать один процент”, `3,5`, `млн/млрд/тыс`. Tartib son faqat год/век va oy nomlari oldida; boshqa kelishiklar
(masalan “с пяти до семи”) va `5-го`, `1990-е` kabi yozuvlar taxminan solishtiriladi.

**Ssenariy yo‘q** belgisi qo‘yilsa, faqat pauza va nafaslar tozalanadi — ssenariy va yozuv tili kerak emas, tovush bo‘yicha ishlaydi.

**Panel tili.** Yuqori o‘ng burchakdagi UZ / RU / EN — panel yozuvlari o‘zbekcha, ruscha yoki inglizcha (tanlov eslab qolinadi).

## Premiere versiyalari bo‘yicha

- Panel ES5 + Promise bilan yozilgan (CEP 7 dagi Chromium uchun), manifest `PPRO [11.0,99.9]`, `CSXS 7.0`.
- `TrackItem.move()` mavjud versiyalarda: QE razor → ortiqcha bo‘laklar ripple’siz o‘chiriladi → saqlanadigan bo‘laklar joyiga suriladi.
  Boshqa treklar siljimaydi. Natija (bo‘sh joylar bilan) keyingi klipga sig‘masa, hech narsa o‘zgartirilmay to‘xtatiladi;
  **Keyingi kliplarni surish** belgilansa, shu trekdagi keyingi kliplar kerakli miqdorda o‘ngga suriladi.
- `move()` bo‘lmagan eski versiyalarda ripple-delete ishlatiladi; bo‘sh joy faqat olib tashlanadigan qism hisobidan ochiladi.
  Bu holatda ripple boshqa treklarga sync-lock bo‘yicha ta’sir qilishi mumkin — panel buni ko‘rsatadi.
- QE DOM rasmiy emas. Har bir API chaqiruvi oldin tekshiriladi; kerakli imkoniyat bo‘lmasa aniq xabar bilan to‘xtaydi.
- 1.1.0 Premiere Pro 23.6 da sinalgan (29 daqiqalik yozuv, qo‘llash 24 s); 1.1.1 dagi nafas tuzatishi faqat o‘sha yozuvda hisoblab tekshirilgan, natija hali eshitilmagan. Avvalgi versiyalar Premiere Pro 2023 (23.x) da sinalgan;
  2017–2022 va 2024+ da qo‘lda sinalmagan. Birinchi ishlatishda muhim bo‘lmagan sequence nusxasida sinab ko‘ring.
- Zaxira nusxa `Sequence.clone()` ga tayanadi; u bo‘lmagan eski versiyada panel “zaxira olinmadi” deb yozadi va davom etadi —
  bunda sequence’ni avval qo‘lda Duplicate qiling.

## O‘rnatish

### Internetsiz kompyuterga (tayyor o‘rnatuvchi)
`dist\offline-<versiya>` papkasini to‘liq ko‘chiring (`SmartVoiceEditor-Setup.exe` va barcha `SmartVoiceEditor.data.0xx`
bo‘laklari; har biri 1.9 GB dan kichik — FAT32 fleshkaga ham sig‘adi), Premiere’ni yoping va Setup.exe ni ishga tushiring.
Ichida Python, barcha kutubxonalar (CUDA bilan), o‘zbekcha modellar va Whisper Medium (ruscha va inglizcha) bor — internet va
administrator huquqi kerak emas. Sukut bo‘yicha `%LOCALAPPDATA%\SmartVoiceEditor` ga o‘rnatiladi.
O‘rnatuvchini yig‘ish (shu kompyuterda, modellar yuklangan bo‘lishi kerak):
`powershell -NoProfile -ExecutionPolicy Bypass -File tools\build_offline.ps1`.

### Internet bor kompyuterga (onlayn o‘rnatuvchi)
https://github.com/Otajon2300/smart-voice-editor/releases/latest/download/SmartVoiceEditor-Online-Setup.exe ni yuklab,
Premiere’ni yoping va ishga tushiring. U eng yangi versiyani (SHA256 bilan), Python 3.12 ni (python.org NuGet paketi,
tizimga o‘rnatilmaydi), kutubxonalarni (NVIDIA drayveri bo‘lsa CUDA bilan) va tanlangan modellarni yuklab, panelni
Premiere’ga ulaydi. Administrator huquqi kerak emas. Oynasiz: `SmartVoiceEditor-Online-Setup.exe /silent "<papka>" uz ru`
(jurnal `<papka>.install.log`, muvaffaqiyatda chiqish kodi 0). Exe imzolanmagan: Windows SmartScreen ogohlantirsa
«More info → Run anyway».

### Yangilanish (GitHub)
Internet bo‘lsa, panel ochilganda https://github.com/Otajon2300/smart-voice-editor dagi oxirgi relizni tekshiradi va
«Yangilash» tugmasini ko‘rsatadi (pastdagi «Yangilanishni tekshirish» bilan qo‘lda ham). Faqat dastur fayllari almashadi
(SHA256 tekshiriladi); Python, modellar va kesh joyida qoladi. Yangi versiya chiqarish: versiyani hamma joyda ko‘taring
(`backend\server.py`, `extension\panel.js`, `extension\host.jsx`, `extension\index.html`, `extension\CSXS\manifest.xml`,
`README.md`), keyin `powershell -NoProfile -ExecutionPolicy Bypass -File tools\release.ps1 -Notes "nima o‘zgardi"`.

### Manbadan (internet bilan)
Windows 8.1/10/11, Python 3.10–3.12, CEP mavjud Premiere. ZIP’ni doimiy papkaga ochib **setup.cmd** ni ishga tushiring:
panel CEP papkasiga ulanadi (`mklink /J`), HKCU `CSXS.7`–`CSXS.16` uchun `PlayerDebugMode=1` yoziladi, Python muhiti tayyorlanadi.
Keyin papkani ko‘chirmang (ko‘chirsangiz setup.cmd ni qayta ishga tushiring). Birinchi o‘rnatish va modellar uchun internet kerak.
O‘chirish: **uninstall.cmd** (panel havolasini olib tashlaydi va backendni to‘xtatadi; papka va modellar qoladi).

Windows 7 qo‘llanmaydi: kerakli Python va nutq kutubxonalari Windows 7 da ishlamaydi. Premiere 2017 ni Windows 10 da ishlating.

NVIDIA GPU uchun: `powershell -NoProfile -ExecutionPolicy Bypass -File .\install-gpu.ps1`. GPU ishlamasa avtomatik CPU ishlatiladi.

Modellar (birinchi ishlatilganda yuklanadi): o‘zbekcha Kotib Medium ≈3.06 GB (SHA256 bir marta tekshiriladi), o‘zbekcha Small ≈0.47 GB,
ruscha/ko‘p tilli Whisper Medium ≈1.5 GB. Audio internetga yuborilmaydi. Tanib olingan matn `.cache/transcripts` da saqlanadi:
o‘sha audio qayta tahlil qilinsa ASR qayta ishlamaydi. Uzun (10 daqiqadan ortiq) MOV/MP4/MXF/WAV fayldan kichik qism tanlansa,
fayl to‘liq emas, faqat shu qism dekodlanadi.

GPU xotirasi yetmasa yoki CUDA kutubxonasi topilmasa, tahlil o‘sha zahoti CPU’da davom etadi. 2 GB li kartalarda Medium modeli
odatda sig‘maydi — bunda CPU yoki Small modeli tezroq.

Backend panel tomonidan yashirin (`pythonw`) ishga tushadi va 30 daqiqa so‘rov bo‘lmasa o‘zi yopiladi.

## Tekshirish

- Python: `.\.venv\Scripts\python.exe -m unittest discover -s tests -q`
- Host (Premiere DOM taqlidi): `node tests/test_host.cjs`
- Panel (CEP’siz, soxta DOM): `node tests/test_panel.cjs`
- Paket: `powershell -NoProfile -ExecutionPolicy Bypass -File tools\build_dist.ps1` → `dist\SmartVoiceEditor-<versiya>.zip` va `.sha256`
  (avval hamma testlarni ishga tushiradi va versiya hamma faylda bir xilligini tekshiradi)
- Haqiqiy fayl bilan to‘liq tahlil, natija WAV bilan:
  `.\.venv\Scripts\python.exe tools\run_real.py --audio ovoz.wav --script s1.docx [--script s2.docx] --out evaluation\real\nom [--cpu]`
- Sun’iy o‘lchov (toza yozuvga qayta o‘qish, duduqlanish va uzun pauzalar qo‘shiladi, keyin natija tekshiriladi):
  `.\.venv\Scripts\python.exe tools\bench.py --audio evaluation\real\uzb.wav --words evaluation\bench\uzb-words.json --out evaluation\bench\run1 --cpu`

Moslik foizi ASR ko‘rsatkichi, inson tasdiqlagan montaj sifati emas. Kesimlarni eshitib tekshiring.
