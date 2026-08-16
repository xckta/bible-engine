from __future__ import annotations

from dataclasses import dataclass

CANONICAL_BOOKS = [
    "Genesis", "Exodus", "Leviticus", "Numbers", "Deuteronomy", "Joshua", "Judges", "Ruth",
    "1 Samuel", "2 Samuel", "1 Kings", "2 Kings", "1 Chronicles", "2 Chronicles", "Ezra", "Nehemiah",
    "Esther", "Job", "Psalms", "Proverbs", "Ecclesiastes", "Song of Solomon", "Isaiah", "Jeremiah",
    "Lamentations", "Ezekiel", "Daniel", "Hosea", "Joel", "Amos", "Obadiah", "Jonah", "Micah", "Nahum",
    "Habakkuk", "Zephaniah", "Haggai", "Zechariah", "Malachi", "Matthew", "Mark", "Luke", "John", "Acts",
    "Romans", "1 Corinthians", "2 Corinthians", "Galatians", "Ephesians", "Philippians", "Colossians",
    "1 Thessalonians", "2 Thessalonians", "1 Timothy", "2 Timothy", "Titus", "Philemon", "Hebrews", "James",
    "1 Peter", "2 Peter", "1 John", "2 John", "3 John", "Jude", "Revelation",
]

# The WEB Ecumenical Edition contains these works in addition to the 66-book Protestant canon.
# Their canonical status varies by Christian tradition; Bible Engine always labels them separately.
DEUTEROCANON_BOOKS = [
    "Tobit", "Judith", "Greek Esther", "Wisdom", "Sirach", "Baruch", "Letter of Jeremiah",
    "Prayer of Azariah", "Susanna", "Bel and the Dragon", "1 Maccabees", "2 Maccabees",
    "1 Esdras", "Prayer of Manasseh", "Psalm 151", "3 Maccabees", "2 Esdras", "4 Maccabees",
]

ALL_BIBLICAL_WORKS = CANONICAL_BOOKS + DEUTEROCANON_BOOKS
BOOK_ORDER = {b: i + 1 for i, b in enumerate(ALL_BIBLICAL_WORKS)}
CANONICAL_SET = set(CANONICAL_BOOKS)
DEUTEROCANON_SET = set(DEUTEROCANON_BOOKS)

USFM_CODES = {
    # canonical
    "GEN":"Genesis", "EXO":"Exodus", "LEV":"Leviticus", "NUM":"Numbers", "DEU":"Deuteronomy",
    "JOS":"Joshua", "JDG":"Judges", "RUT":"Ruth", "1SA":"1 Samuel", "2SA":"2 Samuel",
    "1KI":"1 Kings", "2KI":"2 Kings", "1CH":"1 Chronicles", "2CH":"2 Chronicles", "EZR":"Ezra",
    "NEH":"Nehemiah", "EST":"Esther", "JOB":"Job", "PSA":"Psalms", "PRO":"Proverbs",
    "ECC":"Ecclesiastes", "SNG":"Song of Solomon", "ISA":"Isaiah", "JER":"Jeremiah",
    "LAM":"Lamentations", "EZK":"Ezekiel", "DAN":"Daniel", "HOS":"Hosea", "JOL":"Joel",
    "AMO":"Amos", "OBA":"Obadiah", "JON":"Jonah", "MIC":"Micah", "NAM":"Nahum", "HAB":"Habakkuk",
    "ZEP":"Zephaniah", "HAG":"Haggai", "ZEC":"Zechariah", "MAL":"Malachi", "MAT":"Matthew",
    "MRK":"Mark", "LUK":"Luke", "JHN":"John", "ACT":"Acts", "ROM":"Romans", "1CO":"1 Corinthians",
    "2CO":"2 Corinthians", "GAL":"Galatians", "EPH":"Ephesians", "PHP":"Philippians", "COL":"Colossians",
    "1TH":"1 Thessalonians", "2TH":"2 Thessalonians", "1TI":"1 Timothy", "2TI":"2 Timothy",
    "TIT":"Titus", "PHM":"Philemon", "HEB":"Hebrews", "JAS":"James", "1PE":"1 Peter",
    "2PE":"2 Peter", "1JN":"1 John", "2JN":"2 John", "3JN":"3 John", "JUD":"Jude", "REV":"Revelation",
    # deuterocanon / apocrypha (USFM standard codes used by WEB distributions)
    "TOB":"Tobit", "JDT":"Judith", "ESG":"Greek Esther", "WIS":"Wisdom", "SIR":"Sirach",
    "BAR":"Baruch", "LJE":"Letter of Jeremiah", "S3Y":"Prayer of Azariah", "SUS":"Susanna",
    "BEL":"Bel and the Dragon", "1MA":"1 Maccabees", "2MA":"2 Maccabees", "1ES":"1 Esdras",
    "MAN":"Prayer of Manasseh", "PS2":"Psalm 151", "3MA":"3 Maccabees", "2ES":"2 Esdras",
    "4MA":"4 Maccabees",
}

ALIASES = {
    "gen":"Genesis", "ge":"Genesis", "gn":"Genesis", "ex":"Exodus", "exo":"Exodus", "lev":"Leviticus",
    "num":"Numbers", "deut":"Deuteronomy", "dt":"Deuteronomy", "1 sam":"1 Samuel", "2 sam":"2 Samuel",
    "1 ki":"1 Kings", "2 ki":"2 Kings", "1 chr":"1 Chronicles", "2 chr":"2 Chronicles",
    "ps":"Psalms", "psalm":"Psalms", "prov":"Proverbs", "eccl":"Ecclesiastes",
    "song":"Song of Solomon", "sos":"Song of Solomon", "isa":"Isaiah", "jer":"Jeremiah",
    "ezek":"Ezekiel", "dan":"Daniel", "matt":"Matthew", "mt":"Matthew", "mk":"Mark", "lk":"Luke",
    "jn":"John", "rom":"Romans", "1cor":"1 Corinthians", "2cor":"2 Corinthians",
    "1 cor":"1 Corinthians", "2 cor":"2 Corinthians", "gal":"Galatians", "eph":"Ephesians",
    "phil":"Philippians", "col":"Colossians", "1thess":"1 Thessalonians", "2thess":"2 Thessalonians",
    "1tim":"1 Timothy", "2tim":"2 Timothy", "heb":"Hebrews", "jas":"James", "1pet":"1 Peter",
    "2pet":"2 Peter", "1jn":"1 John", "2jn":"2 John", "3jn":"3 John", "rev":"Revelation",
    # deuterocanon
    "tob":"Tobit", "tobias":"Tobit", "jdt":"Judith", "wis":"Wisdom", "wisdom of solomon":"Wisdom",
    "sir":"Sirach", "ecclesiasticus":"Sirach", "ben sira":"Sirach", "letter jeremiah":"Letter of Jeremiah",
    "epistle of jeremiah":"Letter of Jeremiah", "prayer azariah":"Prayer of Azariah", "song three":"Prayer of Azariah",
    "bel":"Bel and the Dragon", "1 macc":"1 Maccabees", "2 macc":"2 Maccabees", "3 macc":"3 Maccabees",
    "4 macc":"4 Maccabees", "1 esd":"1 Esdras", "2 esd":"2 Esdras", "4 ezra":"2 Esdras",
    "prayer manasseh":"Prayer of Manasseh", "ps 151":"Psalm 151", "greek esther":"Greek Esther",
}

for name in ALL_BIBLICAL_WORKS:
    ALIASES.setdefault(name.lower(), name)


@dataclass(frozen=True)
class ReferenceWork:
    code: str
    name: str
    category: str
    relevance: str
    source_label: str
    source_url: str
    public_domain: bool = True


REFERENCE_WORKS = [
    ReferenceWork("1ENOCH", "1 Enoch", "Second Temple / Pseudepigrapha", "Very high NT/Jude relevance", "R. H. Charles (1913/1917)", "https://ccel.org/c/charles/otpseudepig/enoch.htm"),
    ReferenceWork("JUB", "Jubilees", "Second Temple / Pseudepigrapha", "High Second Temple worldview relevance", "R. H. Charles (1913)", "https://ccel.org/ccel/c/charles/otpseudepig/files/jubilee/1.htm"),
    ReferenceWork("ASMOS", "Assumption of Moses", "Second Temple / Pseudepigrapha", "Very high Jude 9 relevance", "R. H. Charles tradition / public-domain source", "https://ccel.org/ccel/deane/pseudepig/pseudepig.vi.ii.html"),
    ReferenceWork("2BAR", "2 Baruch", "Second Temple / Pseudepigrapha", "High apocalyptic context relevance", "Public-domain scholarly translation", "https://ccel.org/ccel/deane/pseudepig/pseudepig.vi.iii.html"),
    ReferenceWork("PSSOL", "Psalms of Solomon", "Second Temple / Pseudepigrapha", "High messianic expectation relevance", "Public-domain scholarly translation/context", "https://ccel.org/ccel/deane/pseudepig.v.i.html"),
    ReferenceWork("T12", "Testaments of the Twelve Patriarchs", "Second Temple / Pseudepigrapha", "High ethical/messianic context relevance", "Public-domain scholarly translation", "https://ccel.org/ccel/deane/pseudepig/pseudepig.vi.iv.html"),
    ReferenceWork("ASCISA", "Ascension / Martyrdom of Isaiah", "Jewish-Christian / Pseudepigrapha", "Moderate-high Hebrews/early Christian context", "R. H. Charles collection", "https://ccel.org/c/charles/otpseudepig/martisah.htm"),
    ReferenceWork("ARISTEAS", "Letter of Aristeas", "Hellenistic Jewish", "High Septuagint/Hellenistic Jewish context", "Andrews in R. H. Charles (1913)", "https://ccel.org/c/charles/otpseudepig/aristeas.htm"),
    ReferenceWork("APCMOS", "Apocalypse of Moses", "Adam literature / Pseudepigrapha", "Moderate anthropology/fall tradition relevance", "R. H. Charles collection", "https://ccel.org/c/charles/otpseudepig/apcmose.htm"),
    ReferenceWork("SLAE", "Slavonic Life of Adam and Eve", "Adam literature / Pseudepigrapha", "Moderate anthropology/fall tradition relevance", "R. H. Charles collection", "https://ccel.org/c/charles/otpseudepig/slanev.htm"),
    ReferenceWork("ADAMEVE", "Books of Adam and Eve", "Adam literature / Pseudepigrapha", "Moderate anthropology/fall tradition relevance", "R. H. Charles collection", "https://ccel.org/c/charles/otpseudepig/adamnev.htm"),
    ReferenceWork("SIB", "Sibylline Oracles", "Jewish/Christian Oracular Literature", "Context for apocalyptic reception", "Milton S. Terry (1899)", "https://www.sacred-texts.com/cla/sib/"),
    ReferenceWork("2ENOCH", "2 Enoch", "Second Temple / Pseudepigrapha", "Apocalyptic/heavenly-tour context", "R. H. Charles collection", "https://www.ccel.org/c/charles/otpseudepig/home.html"),
    ReferenceWork("3BAR", "3 Baruch", "Second Temple / Pseudepigrapha", "Apocalyptic context", "R. H. Charles collection", "https://www.ccel.org/c/charles/otpseudepig/home.html"),
]
REFERENCE_BY_CODE = {w.code: w for w in REFERENCE_WORKS}
REFERENCE_BY_NAME = {w.name.lower(): w for w in REFERENCE_WORKS}


def normalize_book(raw: str) -> str | None:
    key = " ".join(raw.strip().replace(".", "").split()).lower()
    compact = key.replace(" ", "")
    return ALIASES.get(key) or ALIASES.get(compact)


def tier_for_book(book: str) -> str:
    if book in CANONICAL_SET:
        return "canonical"
    if book in DEUTEROCANON_SET:
        return "deuterocanon"
    return "reference"
