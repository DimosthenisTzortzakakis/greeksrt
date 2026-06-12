from __future__ import annotations
from typing import List, Dict, Optional

# ── Greek grammar rules ──────────────────────────────────────────────────────

# Never let these words be the LAST word of a subtitle
GREEK_NO_END = frozenset({
    'και', 'αλλά', 'αλλα', 'ή', 'ούτε', 'ουτε', 'μήτε', 'μητε', 'είτε', 'ειτε', 'μα',
    'όμως', 'ομως', 'ωστόσο', 'ωστοσο', 'εντούτοις', 'εντουτοις',
    'γιατί', 'γιατι', 'διότι', 'διοτι', 'επειδή', 'επειδη',
    'αφού', 'αφου', 'αν', 'εάν', 'εαν',
    'όταν', 'οταν', 'μόλις', 'μολις', 'ενώ', 'ενω', 'καθώς', 'καθως',
    'να', 'θα', 'ας', 'μη', 'μην',
    'που', 'οπού', 'οπου', 'όπου', 'όπως', 'οπως',
    # degree/quantity adverbs that bind to the word AFTER them ("πιο μικρά")
    'πιο', 'πολύ', 'πολυ', 'τόσο', 'τοσο', 'λίγο', 'λιγο',
    'αρκετά', 'αρκετα', 'σχεδόν', 'σχεδον', 'εντελώς', 'εντελως',
})

# Splitting BEFORE these words is GOOD — they start a new clause/phrase
# ("που κατάφερε…", "για να μεγαλώσει", "όταν ήρθε…")
GREEK_CLAUSE_START = frozenset({
    'που', 'για', 'όταν', 'οταν', 'αν', 'εάν', 'εαν', 'επειδή', 'επειδη',
    'ότι', 'οτι', 'πως', 'και', 'αλλά', 'αλλα', 'ενώ', 'ενω',
    'καθώς', 'καθως', 'μόλις', 'μολις', 'αφού', 'αφου', 'γιατί', 'γιατι',
    'στο', 'στη', 'στην', 'στον', 'στις', 'στα', 'στους',
    'με', 'από', 'απο', 'χωρίς', 'χωρις',
})
ENGLISH_CLAUSE_START = frozenset({
    'that', 'which', 'when', 'because', 'and', 'but', 'so',
    'for', 'with', 'to', 'in', 'on', 'if', 'while',
})

# Never let these words be the LAST word of a subtitle (articles/prepositions alone look bad)
GREEK_NO_BREAK_AFTER = frozenset({
    'ο', 'η', 'το', 'οι', 'τα', 'τον', 'την', 'τους', 'τις',
    'ένας', 'ενας', 'μία', 'μια', 'ένα', 'ενα',
    'από', 'απο', 'για', 'με', 'σε', 'κατά', 'κατα',
    'μέχρι', 'μεχρι', 'ως', 'εως', 'προς', 'χωρίς', 'χωρις', 'παρά', 'παρα',
    'αυτός', 'αυτος', 'αυτή', 'αυτη', 'αυτό', 'αυτο',
    'αυτοί', 'αυτοι', 'αυτές', 'αυτες', 'αυτά', 'αυτα',
    'κάθε', 'καθε',
})

# Avoid starting a subtitle with pure particles (verb clitics).
# Prepositions like "για/με/σε" are FINE starters — they open a new phrase.
GREEK_NO_START = frozenset({
    'να', 'θα', 'ας', 'μη', 'μην',
})

ENGLISH_NO_END  = frozenset({'and', 'but', 'or', 'nor', 'yet', 'so', 'because', 'since', 'that', 'if'})
ENGLISH_NO_AFTER = frozenset({'a', 'an', 'the', 'this', 'that', 'these', 'those', 'to', 'of', 'in', 'on', 'at', 'by', 'for', 'with'})
ENGLISH_NO_START = frozenset({'to', 'of', 'in', 'on', 'at', 'by', 'for', 'with'})

SENTENCE_ENDINGS = {'.', '!', '?', '…', ';'}  # ; = Greek question mark in some fonts


def _norm(word: str) -> str:
    return word.strip().lower().rstrip('.,!?;:«»""\'…—–')


def _ends_sentence(word: str) -> bool:
    return any(word.rstrip().endswith(c) for c in SENTENCE_ENDINGS)


def _silence_before(words: List[Dict], idx: int) -> float:
    if idx == 0:
        return 0.0
    return max(0.0, words[idx]['start'] - words[idx - 1]['end'])


def _split_score(words: List[Dict], idx: int, language: str, silence: float = 0.0) -> int:
    """Score a potential split point before words[idx]. Higher = better."""
    if idx <= 0 or idx >= len(words):
        return 0

    prev = _norm(words[idx - 1]['word'])
    nxt  = _norm(words[idx]['word'])
    no_end   = GREEK_NO_END   if language != 'en' else ENGLISH_NO_END
    no_after = GREEK_NO_BREAK_AFTER if language != 'en' else ENGLISH_NO_AFTER
    no_start = GREEK_NO_START if language != 'en' else ENGLISH_NO_START

    clause_start = GREEK_CLAUSE_START if language != 'en' else ENGLISH_CLAUSE_START

    score = 0
    if _ends_sentence(words[idx - 1]['word']):
        score += 100
    if words[idx - 1]['word'].rstrip().endswith(','):
        score += 25
    if silence >= 0.3:
        score += int(silence * 30)
    if nxt in clause_start:
        score += 40

    if prev in no_end:
        score -= 90
    if prev in no_after:
        score -= 75
    if nxt in no_start:
        score -= 60

    return score


def _best_split_idx(words: List[Dict], language: str) -> int:
    """Find the best index to split a word list into two parts."""
    mid = len(words) // 2
    best_idx, best_score = mid, -10000

    # Never leave a 1-word orphan on either side when avoidable
    lo = 2 if len(words) >= 4 else 1
    hi = len(words) - 1 if len(words) >= 4 else len(words)

    for i in range(lo, hi):
        silence = _silence_before(words, i)
        score = _split_score(words, i, language, silence)
        score -= abs(i - mid) * 3  # prefer splits near the middle
        if score > best_score:
            best_score, best_idx = score, i

    return best_idx


def _split_long(words: List[Dict], max_chars: int, language: str, depth: int = 0) -> List[List[Dict]]:
    """Recursively split a word list until each part fits within max_chars."""
    if depth > 4 or len(words) <= 1:
        return [words]

    text = ' '.join(w['word'] for w in words)
    if len(text) <= max_chars:
        return [words]

    idx = _best_split_idx(words, language)
    left  = words[:idx]
    right = words[idx:]

    return (
        _split_long(left,  max_chars, language, depth + 1) +
        _split_long(right, max_chars, language, depth + 1)
    )


def _two_lines(text: str, max_chars: int, language: str) -> str:
    """If text > max_chars, split into 2 balanced lines at a grammatically safe point."""
    if len(text) <= max_chars:
        return text

    words_list = text.split()
    if len(words_list) <= 1:
        return text

    no_end   = GREEK_NO_END   if language != 'en' else ENGLISH_NO_END
    no_after = GREEK_NO_BREAK_AFTER if language != 'en' else ENGLISH_NO_AFTER
    no_start = GREEK_NO_START if language != 'en' else ENGLISH_NO_START

    mid = len(text) // 2
    best_idx, best_score = -1, None

    acc = 0
    for i in range(len(words_list) - 1):
        acc += len(words_list[i]) + 1
        cur = _norm(words_list[i])
        nxt = _norm(words_list[i + 1])

        penalty = 0
        if cur in no_end:   penalty += 90
        if cur in no_after: penalty += 75
        if nxt in no_start: penalty += 60

        score = (abs(acc - mid) + penalty,)
        if best_score is None or score < best_score:
            best_score, best_idx = score, i

    if best_idx < 0:
        return text

    line1 = ' '.join(words_list[:best_idx + 1]).strip()
    line2 = ' '.join(words_list[best_idx + 1:]).strip()
    return f"{line1}\n{line2}"


# ── Public API ────────────────────────────────────────────────────────────────

def create_subtitles(
    words: List[Dict],
    silence_threshold: float = 0.5,
    max_chars: int = 80,
    language: str = 'el',
) -> List[Dict]:
    """
    Sentence-first algorithm:
      1. Hard breaks on: sentence endings, pauses, speaker changes
      2. Recursively split any segment that still exceeds max_chars
      3. Format as 1- or 2-line subtitle cards
    Returns a list of {start, end, text, speaker} dicts.
    """
    if not words:
        return []

    # ── Step 1: hard breaks ───────────────────────────────────────────────────
    raw_segments: List[List[Dict]] = []
    current: List[Dict] = []

    for i, word in enumerate(words):
        w_text = word.get('word') or word.get('text') or ''
        if not w_text.strip():
            continue

        if current:
            silence = _silence_before(words, i)
            prev    = current[-1]
            speaker_change = (
                word.get('speaker_id') is not None
                and prev.get('speaker_id') is not None
                and word['speaker_id'] != prev['speaker_id']
            )
            sentence_end = _ends_sentence(prev.get('word') or prev.get('text') or '')
            force = silence >= silence_threshold or speaker_change or sentence_end

            if force:
                raw_segments.append(current)
                current = [word]
                continue

        current.append(word)

    if current:
        raw_segments.append(current)

    # ── Step 2: split long segments ───────────────────────────────────────────
    final_groups: List[List[Dict]] = []
    for seg in raw_segments:
        text = ' '.join(w.get('word') or w.get('text') or '' for w in seg)
        if len(text) > max_chars:
            final_groups.extend(_split_long(seg, max_chars, language))
        else:
            final_groups.append(seg)

    # ── Step 2b: absorb tiny fragments into a neighbour ───────────────────────
    final_groups = _merge_tiny_groups(final_groups, max_chars, silence_threshold)

    # ── Step 3: build subtitle objects ────────────────────────────────────────
    subtitles: List[Dict] = []
    for group in final_groups:
        if not group:
            continue
        text = ' '.join(
            (w.get('word') or w.get('text') or '') for w in group
        ).strip()
        text = _two_lines(text, max_chars, language)

        subtitles.append({
            'start':   group[0]['start'],
            'end':     group[-1]['end'],
            'text':    text,
            'speaker': group[0].get('speaker_id'),
        })

    # ── Step 4: merge overlapping speakers into stacked subtitle blocks ────────
    subtitles = _merge_overlapping_speakers(subtitles)

    return subtitles


def _group_text(group: List[Dict]) -> str:
    return ' '.join((w.get('word') or w.get('text') or '') for w in group).strip()


def _same_speaker(a: List[Dict], b: List[Dict]) -> bool:
    sa, sb = a[0].get('speaker_id'), b[0].get('speaker_id')
    return sa is None or sb is None or sa == sb


def _merge_tiny_groups(
    groups: List[List[Dict]],
    max_chars: int,
    silence_threshold: float,
) -> List[List[Dict]]:
    """
    A 1-word / very short card ("χώρα") reads terribly. Glue it onto the
    neighbour it most likely belongs to, as long as the result still fits
    on two lines and there is no real pause between them.
    """
    min_len = max(8, max_chars // 4)
    changed = True
    while changed and len(groups) > 1:
        changed = False
        for i, g in enumerate(groups):
            text = _group_text(g)
            if len(g) > 1 and len(text) >= min_len:
                continue

            candidates = []
            if i > 0:
                prev = groups[i - 1]
                gap = g[0]['start'] - prev[-1]['end']
                combined = len(_group_text(prev)) + 1 + len(text)
                if gap < silence_threshold and combined <= max_chars * 2 and _same_speaker(prev, g):
                    candidates.append(('prev', combined))
            if i + 1 < len(groups):
                nxt = groups[i + 1]
                gap = nxt[0]['start'] - g[-1]['end']
                combined = len(text) + 1 + len(_group_text(nxt))
                if gap < silence_threshold and combined <= max_chars * 2 and _same_speaker(g, nxt):
                    candidates.append(('next', combined))

            if not candidates:
                continue
            # Merge into whichever side stays shorter
            side = min(candidates, key=lambda c: c[1])[0]
            if side == 'prev':
                groups[i - 1] = groups[i - 1] + g
            else:
                groups[i + 1] = g + groups[i + 1]
            del groups[i]
            changed = True
            break
    return groups


def _merge_overlapping_speakers(subtitles: List[Dict]) -> List[Dict]:
    """
    When two consecutive subtitles from *different* speakers overlap in time
    (i.e. speaker B starts before speaker A finishes), stack them into a single
    dual-line subtitle block so both voices are visible simultaneously.
    """
    if len(subtitles) < 2:
        return subtitles

    result: List[Dict] = []
    i = 0
    while i < len(subtitles):
        sub = subtitles[i]
        if i + 1 < len(subtitles):
            nxt = subtitles[i + 1]
            # Overlap: next starts before current ends, different speakers
            different_speakers = (
                sub.get('speaker') is not None
                and nxt.get('speaker') is not None
                and sub['speaker'] != nxt['speaker']
            )
            time_overlap = nxt['start'] < sub['end']
            if different_speakers and time_overlap:
                result.append({
                    'start':   min(sub['start'], nxt['start']),
                    'end':     max(sub['end'],   nxt['end']),
                    'text':    sub['text'] + '\n' + nxt['text'],
                    'speaker': None,  # dual-speaker block has no single speaker
                })
                i += 2
                continue
        result.append(sub)
        i += 1
    return result


def subtitles_to_srt(
    subtitles: List[Dict],
    keep_connected: bool = True,
    silence_threshold: float = 0.5,
    min_duration: float = 0.8,
) -> str:
    """Convert subtitle dicts to SRT string."""
    parts: List[str] = []
    for i, sub in enumerate(subtitles):
        start = sub['start']
        word_end = sub['end']

        if keep_connected and i + 1 < len(subtitles):
            gap = subtitles[i + 1]['start'] - word_end
            end = subtitles[i + 1]['start'] if gap < silence_threshold else word_end
        else:
            end = word_end

        end = max(end, start + min_duration)

        parts.append(str(i + 1))
        parts.append(f"{_fmt_time(start)} --> {_fmt_time(end)}")
        parts.append(sub['text'])
        parts.append('')

    return '\n'.join(parts)


def _fmt_time(seconds: float) -> str:
    total_ms = int(round(seconds * 1000))
    ms = total_ms % 1000
    s  = (total_ms // 1000) % 60
    m  = (total_ms // 60000) % 60
    h  = total_ms // 3600000
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def normalize_words(raw_words: List[Dict]) -> List[Dict]:
    """Normalize word format from different providers to {word, start, end, speaker_id?}."""
    out = []
    for w in raw_words:
        # ElevenLabs uses 'text' and 'type'; Groq/OpenAI use 'word'
        if w.get('type') in ('spacing', 'audio_event'):
            continue
        text = (w.get('word') or w.get('text') or '').strip()
        if not text:
            continue
        out.append({
            'word':       text,
            'start':      float(w.get('start') or 0),
            'end':        float(w.get('end') or 0),
            'speaker_id': w.get('speaker_id'),
        })
    return out


def segments_to_words(segments: List[Dict]) -> List[Dict]:
    """Fallback: distribute segment text evenly when word timestamps unavailable."""
    words = []
    for seg in segments:
        seg_words = seg.get('text', '').split()
        if not seg_words:
            continue
        dur = (seg['end'] - seg['start']) / len(seg_words)
        for i, w in enumerate(seg_words):
            words.append({
                'word':  w,
                'start': seg['start'] + i * dur,
                'end':   seg['start'] + (i + 1) * dur,
            })
    return words
