from __future__ import annotations

BOOKS = [
    "Genesis","Exodus","Leviticus","Numbers","Deuteronomy","Joshua","Judges","Ruth",
    "1 Samuel","2 Samuel","1 Kings","2 Kings","1 Chronicles","2 Chronicles","Ezra","Nehemiah",
    "Esther","Job","Psalms","Proverbs","Ecclesiastes","Song of Solomon","Isaiah","Jeremiah",
    "Lamentations","Ezekiel","Daniel","Hosea","Joel","Amos","Obadiah","Jonah","Micah","Nahum",
    "Habakkuk","Zephaniah","Haggai","Zechariah","Malachi","Matthew","Mark","Luke","John","Acts",
    "Romans","1 Corinthians","2 Corinthians","Galatians","Ephesians","Philippians","Colossians",
    "1 Thessalonians","2 Thessalonians","1 Timothy","2 Timothy","Titus","Philemon","Hebrews","James",
    "1 Peter","2 Peter","1 John","2 John","3 John","Jude","Revelation",
]

ALIASES = {
    "gen":"Genesis","ge":"Genesis","gn":"Genesis","ex":"Exodus","exo":"Exodus","lev":"Leviticus",
    "1 sam":"1 Samuel","2 sam":"2 Samuel","1 ki":"1 Kings","2 ki":"2 Kings","1 chr":"1 Chronicles","2 chr":"2 Chronicles",
    "num":"Numbers","deut":"Deuteronomy","dt":"Deuteronomy","ps":"Psalms","psalm":"Psalms",
    "psalms":"Psalms","prov":"Proverbs","eccl":"Ecclesiastes","song":"Song of Solomon","sos":"Song of Solomon",
    "isa":"Isaiah","jer":"Jeremiah","ezek":"Ezekiel","dan":"Daniel","matt":"Matthew","mt":"Matthew",
    "mk":"Mark","lk":"Luke","jn":"John","rom":"Romans","1cor":"1 Corinthians","2cor":"2 Corinthians",
    "1 cor":"1 Corinthians","2 cor":"2 Corinthians","1 th":"1 Thessalonians","2 th":"2 Thessalonians",
    "gal":"Galatians","eph":"Ephesians","phil":"Philippians","col":"Colossians","1thess":"1 Thessalonians",
    "2thess":"2 Thessalonians","1tim":"1 Timothy","2tim":"2 Timothy","1 tim":"1 Timothy","2 tim":"2 Timothy","heb":"Hebrews","jas":"James",
    "1pet":"1 Peter","2pet":"2 Peter","1 pet":"1 Peter","2 pet":"2 Peter","1jn":"1 John","2jn":"2 John","3jn":"3 John",
    "1 jn":"1 John","2 jn":"2 John","3 jn":"3 John","rev":"Revelation",
}

BOOK_SET = {b.lower(): b for b in BOOKS}


def normalize_book(raw: str) -> str | None:
    key = " ".join(raw.strip().replace(".", "").split()).lower()
    compact = key.replace(" ", "")
    return BOOK_SET.get(key) or ALIASES.get(key) or ALIASES.get(compact)
