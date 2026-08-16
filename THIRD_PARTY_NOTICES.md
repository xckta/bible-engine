# Third-party corpus notices

## English Standard Version (ESV)

Bible Engine does not redistribute the ESV corpus. Canonical quotations are requested at runtime from Crossway's official ESV API using the user's own API key. The ESV copyright notice is displayed in the application whenever ESV text is displayed.

## World English Bible (WEB)

The World English Bible source used for local canonical retrieval and the Deuterocanon/Apocrypha shelf is public domain. Source: eBible.org.

## American Standard Version (ASV, 1901)

Public domain. Retained as a local auxiliary corpus/source for compatibility and translation comparison; canonical Oracle quotations are ESV.

## Compact language drawer: unfoldingWord Hebrew Bible (UHB v2.1.32)

The compact Languages drawer downloads the unfoldingWord Hebrew Bible to the user's local `data/sources/original/` directory on first use/startup. It is not committed to this repository. UHB is distributed under CC BY-SA 4.0 and is based on the Open Scriptures Hebrew Bible / Westminster Leningrad Codex tradition.

## Compact language drawer: unfoldingWord Greek New Testament (UGNT v0.34)

The compact Languages drawer downloads the unfoldingWord Greek New Testament locally. It is not committed to this repository. UGNT is distributed under CC BY-SA 4.0 and provides tokenized Koine Greek text with lexical and morphological attributes in USFM 3.0.

## Deep Original Language Lab: Open Scriptures Hebrew Bible / MorphHB

The advanced `/originals` workspace downloads `openscriptures/morphhb` locally. The Westminster Leningrad Codex text is public domain. Open Scriptures Hebrew Bible lemma and morphology data are licensed under CC BY 4.0. Bible Engine also uses the project's VerseMap metadata to avoid silently guessing across WLC/English versification boundaries.

## Deep Original Language Lab: Tischendorf morphology

The advanced Greek layer downloads the public-domain Tischendorf morphology dataset from `morphgnt/tischendorf-data`, credited in the application to Ulrik Petersen, G. Clint Yale, and Maurice A. Robinson.

## Brown–Driver–Briggs / OpenScriptures Hebrew Lexicon

The advanced Hebrew lexical profile downloads `openscriptures/HebrewLexicon`. Brown–Driver–Briggs dictionary text is public domain; OpenScriptures XML/markup and related database work are provided under CC BY 4.0. Bible Engine keeps this richer lexical layer visibly separate from the historical Strong's dictionary layer.

## Strong's Dictionaries

The advanced lab downloads the corrected OpenScriptures e-text of the 1890 Strong's Hebrew and Greek dictionaries. The historical dictionary text is public domain. It is presented as a historical orientation layer, not as the primary semantic authority for a word.

## Septuagint lemma witnesses

The advanced Greek lab downloads lemma-index metadata from `openscriptures/GreekResources` / the Open Scriptures Septuagint Project. Bible Engine indexes lemma occurrence metadata only. It deliberately does **not** bundle or quote the separately licensed CCAT Septuagint text.

## Public-domain reference literature

Bible Engine's reference installer uses public-domain transcriptions/translations from sources such as Christian Classics Ethereal Library (CCEL) and Internet Sacred Text Archive. Individual work metadata is stored in the database and displayed in the Library drawer. Reference texts are never labelled as canonical Scripture.
