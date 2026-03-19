# FridgeFriend
Tīmekļa lietotne, kas palīdz atrast labas receptes tieši no tā, kas jau ir tavā ledusskapī.
Autors: Ailine Erena, 12.B klase

---

1. POSMA ATSKAITE: https://docs.google.com/document/d/18KIzGt6LViMp8-FTW1ae4AYCkutLShjrLp9XqhYPvl8/edit
   
3. IZSTRĀDES APRAKSTS: https://docs.google.com/document/d/1aupAsq8I9Oz1zdjv2Tr4YIPgNXj7zffUED_OIflv7Wc/edit

PREZENTĀCIJA:

PORTFOLIO:


## Projekta struktūra

```
fridgefriend/
├── app.py                    Galvenais Flask fails ar visiem maršrutiem
├── fridgefriend.db           SQLite datubāze
├── requirements.txt          Nepieciešamie Python pakotņi
├── static/
│   └── style.css             Kopējie stili lapām
└── templates/
    ├── base.html             Pamats (navigācija, footer)
    ├── sakums.html           Sākumlapa
    ├── sastavdalas.html      Sastāvdaļu izvēlne
    ├── receptes.html         Meklēšanas rezultāti
    ├── recepte.html          Pilna recepte ar detaļām
    ├── mansledusskapis.html  Mans virtuālais ledusskapis
    ├── login.html            Pieslēgšanās forma
    └── register.html         Reģistrācijas forma
```

## Datubāze

| Tabula | Saturs |
|--------|--------|
| `users` | Lietotāju konti un paroļu jaukšana |
| `ingredients` | Pieejamās sastāvdaļas ar kategorijām |
| `recipes` | Receptes ar apmēram laiku, cenu, grūtības pakāpi |
| `recipe_ingredients` | Kuras sastāvdaļas nepieciešamas katrai receptei |
| `recipe_steps` | Soļi katra receptes pagatavošanai |
| `user_fridge` | Produkti, kurus licis savā ledusskapī |
| `user_favorites` | Saglabātās iecienītākās receptes |

## Sākšana

### Prasības
- Python 3.10 vai jaunāka versija

### Instalācija

1. Lejupielādi Python no [python.org](https://python.org)

2. Instalē nepieciešamos pakotņus:
```bash
pip install -r requirements.txt
```

3. Palaid lietotni:
```bash
python app.py
```

4. Atvēc pārlūkprogrammā un ej uz `http://localhost:5000`

### Darbs ar Visual Studio Code

1. Atver projekta mapi VSCode
2. Instalē Python extension (ja vēl nav)
3. Izvēlies pareizo Python interpreter (3.10+)
4. Terminālī: `python app.py`
5. Kad sāks darbties, pārlūkprogrammā atvērt `http://localhost:5000`

## API galapunkti

| Metode | Galapunkts | Apraksts |
|--------|-----------|---------|
| GET | `/` | Sākumlapa |
| GET | `/sastavdalas` | Visu sastāvdaļu izvēlne |
| POST | `/receptes` | Meklēt receptes pēc atlasītajām sastāvdaļām |
| GET | `/recepte/<id>` | Pilna recepte ar instrukcijām |
| GET | `/mans-ledusskapis` | Rāda manā ledusskapī pievienotos produktus |
| POST | `/mans-ledusskapis/pievienot` | Pievienot produktu ledusskapim |
| POST | `/mans-ledusskapis/dzest/<id>` | Noņemt produktu no ledusskapia |
| GET/POST | `/pieslegt` | Pieslēgšanās lapa |
| GET/POST | `/registreties` | Reģistrācija jauniem lietotājiem |
| GET | `/iziet` | Atrakstīties un iziešana |
| GET | `/api/receptes` | JSON atbilde ar receptēm (bez autentifikācijas) |
| GET | `/api/ledusskapis` | JSON atbilde ar lietotāja produktiem (nepieciešama pieslēgšanās) |
