from __future__ import annotations

import html
import re
import urllib.request
from dataclasses import dataclass
from html.parser import HTMLParser

from .books import ReferenceWork


class ReferenceLibraryError(RuntimeError):
    pass


class _TextExtractor(HTMLParser):
    BLOCK = {"p", "div", "br", "li", "h1", "h2", "h3", "h4", "h5", "h6", "tr", "blockquote", "hr"}
    SKIP = {"script", "style", "nav", "footer", "header", "noscript", "svg"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self._skip = 0

    def handle_starttag(self, tag: str, attrs) -> None:
        tag = tag.lower()
        if tag in self.SKIP:
            self._skip += 1
        if not self._skip and tag in self.BLOCK:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag in self.SKIP and self._skip:
            self._skip -= 1
        if not self._skip and tag in self.BLOCK:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if not self._skip:
            self.parts.append(data)

    def text(self) -> str:
        raw = html.unescape("".join(self.parts)).replace("\xa0", " ")
        lines = [" ".join(x.split()) for x in raw.splitlines()]
        lines = [x for x in lines if x]
        return "\n".join(lines)


def html_to_text(payload: bytes) -> str:
    decoded = payload.decode("utf-8", errors="replace")
    parser = _TextExtractor()
    parser.feed(decoded)
    return parser.text()


def _fetch(url: str, timeout: float = 30.0) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "BibleEngine/0.3 (+local research tool)"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return html_to_text(r.read())
    except Exception as exc:
        raise ReferenceLibraryError(f"Could not download {url}: {exc}") from exc


def _clean_source_text(text: str, title_markers: tuple[str, ...] = ()) -> str:
    lines = [x.strip() for x in text.splitlines() if x.strip()]
    # Drop common site chrome and bibliographic tails without trying to rewrite the source.
    drop_prefixes = (
        "Christian Classics Ethereal Library", "Internet Sacred Text Archive", "Sacred Texts",
        "Home |", "Search |", "Copyright", "From The Apocrypha and Pseudepigrapha",
        "Scanned and Edited by", "Reformatted by", "Chapter:",
    )
    useful: list[str] = []
    started = not title_markers
    for line in lines:
        low = line.lower()
        if title_markers and any(marker.lower() in low for marker in title_markers):
            started = True
        if not started:
            continue
        if line.startswith(drop_prefixes):
            continue
        useful.append(line)
    return "\n".join(useful)


def split_numbered_chapters(text: str, work_name: str) -> list[dict]:
    """Split public-domain transcriptions that mark chapters as `Chapter 6` / `[Chapter 6]`.

    Verse numbers are preserved when present. If they are absent, each chapter is stored as
    one passage rather than inventing verse divisions.
    """
    text = re.sub(r"\[\s*Chapter\s+(\d+)\s*\]", r"\nChapter \1\n", text, flags=re.I)
    matches = list(re.finditer(r"(?im)^\s*Chapter\s+(\d+)\s*$", text))
    if not matches:
        return chunk_text(text, section=work_name)
    out: list[dict] = []
    ordinal = 0
    for i, m in enumerate(matches):
        chapter = int(m.group(1))
        body = text[m.end(): matches[i + 1].start() if i + 1 < len(matches) else len(text)].strip()
        # Many transcriptions have leading verse numerals on lines. Group them conservatively.
        vm = list(re.finditer(r"(?m)^\s*(\d{1,3})[\.\s]+(?=\S)", body))
        if vm and len(vm) >= 2:
            for j, v in enumerate(vm):
                start = v.end()
                end = vm[j + 1].start() if j + 1 < len(vm) else len(body)
                verse = int(v.group(1))
                piece = " ".join(body[start:end].split())
                if piece:
                    ordinal += 1
                    out.append({"chapter": chapter, "verse_start": verse, "verse_end": verse,
                                "section": f"{work_name} {chapter}", "ordinal": ordinal, "text": piece})
        elif body:
            ordinal += 1
            out.append({"chapter": chapter, "verse_start": None, "verse_end": None,
                        "section": f"{work_name} {chapter}", "ordinal": ordinal,
                        "text": " ".join(body.split())})
    return out


def chunk_text(text: str, *, section: str, chapter: int | None = None, max_chars: int = 1400) -> list[dict]:
    paras = [" ".join(x.split()) for x in re.split(r"\n{1,}", text) if len(" ".join(x.split())) >= 30]
    out: list[dict] = []
    buffer = ""
    ordinal = 0
    for para in paras:
        candidate = (buffer + " " + para).strip()
        if buffer and len(candidate) > max_chars:
            ordinal += 1
            out.append({"chapter": chapter, "verse_start": None, "verse_end": None,
                        "section": section, "ordinal": ordinal, "text": buffer})
            buffer = para
        else:
            buffer = candidate
    if buffer:
        ordinal += 1
        out.append({"chapter": chapter, "verse_start": None, "verse_end": None,
                    "section": section, "ordinal": ordinal, "text": buffer})
    return out


@dataclass(frozen=True)
class DownloadSpec:
    work: ReferenceWork
    mode: str
    urls: tuple[str, ...]
    title_markers: tuple[str, ...] = ()


# Primary/public-domain transcriptions where practical. The final three entries are explicitly
# labelled context/fragments when a complete public-domain verse-addressed transcription is not
# available through the same source. We never present those chunks as canonical Scripture.
REFERENCE_SPECS: tuple[DownloadSpec, ...] = (
    DownloadSpec(
        ReferenceWork("1ENOCH", "1 Enoch", "Second Temple / Pseudepigrapha", "Very high NT/Jude relevance",
                      "R. H. Charles, 1913 (public domain)", "https://ccel.org/c/charles/otpseudepig/enoch.htm"),
        "chapters", ("https://ccel.org/c/charles/otpseudepig/enoch.htm",), ("1 Enoch", "Book of Enoch"),
    ),
    DownloadSpec(
        ReferenceWork("JUB", "Jubilees", "Second Temple / Pseudepigrapha", "High Second Temple worldview relevance",
                      "R. H. Charles, 1913 (public domain)", "https://www.ccel.org/ccel/c/charles/otpseudepig/files/jubilee/index.htm"),
        "numbered_pages", tuple(f"https://www.ccel.org/ccel/c/charles/otpseudepig/files/jubilee/{n}.htm" for n in range(1, 51)),
        ("THE BOOK OF JUBILEES",),
    ),
    DownloadSpec(
        ReferenceWork("ASMOS", "Assumption of Moses", "Second Temple / Pseudepigrapha", "Very high Jude 9 relevance",
                      "Public-domain translation transcription", "https://www.sacredthings.org/docs/assumption-1"),
        "numbered_pages", tuple(f"https://www.sacredthings.org/docs/assumption-{n}" for n in range(1, 13)),
        ("Moses", "Chapter"),
    ),
    DownloadSpec(
        ReferenceWork("T12", "Testaments of the Twelve Patriarchs", "Second Temple / Pseudepigrapha", "High ethical/messianic context relevance",
                      "Ante-Nicene Fathers public-domain translation", "https://ccel.org/ccel/anonymous/patriarch_testaments/anf08.iii.iii.html"),
        "numbered_pages",
        tuple(f"https://ccel.org/ccel/anonymous/patriarch_testaments/anf08.iii.{roman}.html" for roman in
              ("iii", "iv", "v", "vi", "vii", "viii", "ix", "x", "xi", "xii", "xiii", "xiv")),
        ("Testament",),
    ),
    DownloadSpec(
        ReferenceWork("ARISTEAS", "Letter of Aristeas", "Hellenistic Jewish", "High Septuagint/Hellenistic Jewish context",
                      "H. T. Andrews in R. H. Charles, 1913", "https://ccel.org/c/charles/otpseudepig/aristeas.htm"),
        "chunks", ("https://ccel.org/c/charles/otpseudepig/aristeas.htm",), ("Letter of Aristeas",),
    ),
    DownloadSpec(
        ReferenceWork("APCMOS", "Apocalypse of Moses", "Adam literature / Pseudepigrapha", "Moderate fall/death tradition relevance",
                      "Public-domain translation in R. H. Charles collection", "https://ccel.org/c/charles/otpseudepig/apcmose.htm"),
        "chapters", ("https://ccel.org/c/charles/otpseudepig/apcmose.htm",), ("Apocalypse of Moses",),
    ),
    DownloadSpec(
        ReferenceWork("ASCISA", "Ascension / Martyrdom of Isaiah", "Jewish-Christian / Pseudepigrapha", "Moderate-high early Jewish/Christian context",
                      "Public-domain translation in R. H. Charles collection", "https://ccel.org/c/charles/otpseudepig/martisah.htm"),
        "chapters", ("https://ccel.org/c/charles/otpseudepig/martisah.htm",), ("Martyrdom of Isaiah",),
    ),
    DownloadSpec(
        ReferenceWork("SLAE", "Slavonic Life of Adam and Eve", "Adam literature / Pseudepigrapha", "Moderate fall/death tradition relevance",
                      "Public-domain translation in R. H. Charles collection", "https://ccel.org/c/charles/otpseudepig/slanev.htm"),
        "chapters", ("https://ccel.org/c/charles/otpseudepig/slanev.htm",), ("Slavonic", "Adam and Eve"),
    ),
    DownloadSpec(
        ReferenceWork("ADAMEVE", "Books of Adam and Eve", "Adam literature / Pseudepigrapha", "Moderate fall/death tradition relevance",
                      "Public-domain translation in R. H. Charles collection", "https://ccel.org/c/charles/otpseudepig/adamnev.htm"),
        "chapters", ("https://ccel.org/c/charles/otpseudepig/adamnev.htm",), ("Adam and Eve",),
    ),
    DownloadSpec(
        ReferenceWork("SIB", "Sibylline Oracles", "Jewish/Christian Oracular Literature", "Context for Jewish and early Christian apocalyptic reception",
                      "Milton S. Terry, 1899 (public domain)", "https://www.sacred-texts.com/cla/sib/"),
        "numbered_pages", tuple(f"https://sacred-texts.com/cla/sib/sib{n:02d}.htm" for n in range(3, 15)),
        ("BOOK", "SIBYLLINE ORACLES"),
    ),
    DownloadSpec(
        ReferenceWork("2BARCTX", "2 Baruch", "Second Temple / Pseudepigrapha", "High apocalyptic context relevance; context/excerpts",
                      "W. J. Deane, 1891 scholarly context/excerpts (public domain)", "https://ccel.org/ccel/deane/pseudepig/pseudepig.vi.iii.html"),
        "chunks", ("https://ccel.org/ccel/deane/pseudepig/pseudepig.vi.iii.html",), ("APOCALYPSE OF BARUCH", "BARUCH"),
    ),
    DownloadSpec(
        ReferenceWork("PSSOLCTX", "Psalms of Solomon", "Second Temple / Pseudepigrapha", "High messianic expectation relevance; context/excerpts",
                      "W. J. Deane, 1891 scholarly context/excerpts (public domain)", "https://ccel.org/ccel/deane/pseudepig/pseudepig.v.i.html"),
        "chunks", ("https://ccel.org/ccel/deane/pseudepig/pseudepig.v.i.html",), ("PSALTER OF SOLOMON",),
    ),
)


def download_spec(spec: DownloadSpec) -> list[dict]:
    passages: list[dict] = []
    ordinal = 0
    if spec.mode == "numbered_pages":
        for chapter, url in enumerate(spec.urls, 1):
            text = _clean_source_text(_fetch(url), spec.title_markers)
            if not text:
                continue
            # SacredThings and several CCEL chapter pages number paragraphs/verses. Preserve them when obvious.
            vm = list(re.finditer(r"(?m)^\s*(\d{1,3})[\.\s]+(?=\S)", text))
            if len(vm) >= 2:
                for j, m in enumerate(vm):
                    piece = " ".join(text[m.end(): vm[j + 1].start() if j + 1 < len(vm) else len(text)].split())
                    if piece:
                        ordinal += 1
                        v = int(m.group(1))
                        passages.append({"chapter": chapter, "verse_start": v, "verse_end": v,
                                         "section": f"{spec.work.name} {chapter}", "ordinal": ordinal, "text": piece})
            else:
                rows = chunk_text(text, section=f"{spec.work.name} {chapter}", chapter=chapter)
                for row in rows:
                    ordinal += 1
                    row["ordinal"] = ordinal
                    passages.append(row)
    else:
        text = "\n".join(_clean_source_text(_fetch(url), spec.title_markers) for url in spec.urls)
        rows = split_numbered_chapters(text, spec.work.name) if spec.mode == "chapters" else chunk_text(text, section=spec.work.name)
        for row in rows:
            ordinal += 1
            row["ordinal"] = ordinal
            passages.append(row)
    if not passages:
        raise ReferenceLibraryError(f"No usable text was extracted for {spec.work.name}.")
    return passages
