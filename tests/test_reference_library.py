from app.reference_library import html_to_text,split_numbered_chapters,chunk_text

def test_html_text_and_chapter_split_unicode():
    raw='<html><body><h1>1 Enoch</h1><p>[Chapter 6]</p><p>1 “Watchers” descended — λόγος.</p><p>2 Second line.</p><p>[Chapter 7]</p><p>1 Next.</p></body></html>'.encode()
    text=html_to_text(raw);rows=split_numbered_chapters(text,'1 Enoch')
    assert any(r['chapter']==6 and 'λόγος' in r['text'] for r in rows)

def test_chunk_text_does_not_invent_verses():
    rows=chunk_text('A long paragraph with enough text to be a reference passage and preserve provenance.','x') if False else chunk_text('A long paragraph with enough text to be a reference passage and preserve provenance.',section='x')
    assert rows and rows[0]['verse_start'] is None
