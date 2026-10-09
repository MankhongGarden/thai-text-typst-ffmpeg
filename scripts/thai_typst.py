"""Compile a Typst file with correct Thai line breaks.

Typst (0.15) breaks Thai with its own dictionary and splits compounds (โรง|พยาบาล, ทุก|คน). This pre-pass
segments every Thai run with PyThaiNLP (newmm) and puts a ZERO WIDTH SPACE between words, then prepends
a show rule that wraps every Thai run (= one word, because ZWSP is outside the Thai block) in an
unbreakable box(). Typst can then break only between words.

Do NOT use WORD JOINER / ZWNBSP between letters instead of box(): Typst 0.15 treats them as break points
inside Thai runs and splits words mid-syllable (ออกกำลั|งกาย) - verified 2026-10-09.

Left untouched: raw text (`...`, ```...```), comments, and string literals that look like file paths.
Keep justify off for Thai: boxes cannot stretch, so justified lines only widen the real spaces.

usage: python thai_typst.py in.typ out.pdf|out.png [--keep] [--ppi 144] [--words "คำ1,คำ2"]
  --keep   also write <in>.th.typ (the processed source) next to the input
  --words  extra words that must never be split (added to the dictionary)
"""
import argparse, os, re, subprocess, sys, tempfile

from pythainlp.tokenize import Tokenizer
from pythainlp.corpus.common import thai_words

TYPST = os.environ.get("TYPST", "typst")
THAI_RUN = re.compile(r"[\u0E00-\u0E7F]+")
ZWSP = "\u200b"
SHOW = '#show regex("[\\u{0E00}-\\u{0E7F}]+"): it => box(it)\n'
SKIP = re.compile(r"```.*?```|`[^`]*`|/\*.*?\*/|//[^\n]*|\"(?:[^\"\\\n]|\\.)*\"", re.S)
PATHLIKE = re.compile(r"[/\\]|\.\w{1,5}\"$")


def segment(text, tok):
    words = lambda m: ZWSP.join(tok.word_tokenize(m.group(0)))
    out, pos = [], 0
    for m in SKIP.finditer(text):
        out.append(THAI_RUN.sub(words, text[pos:m.start()]))
        s = m.group(0)
        out.append(THAI_RUN.sub(words, s) if s.startswith('"') and not PATHLIKE.search(s) else s)
        pos = m.end()
    out.append(THAI_RUN.sub(words, text[pos:]))
    return SHOW + "".join(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src")
    ap.add_argument("out")
    ap.add_argument("--keep", action="store_true")
    ap.add_argument("--ppi", default="144")
    ap.add_argument("--words", default="")
    a = ap.parse_args()
    extra = {w.strip() for w in a.words.split(",") if w.strip()}
    tok = Tokenizer(set(thai_words()) | extra, engine="newmm")
    with open(a.src, encoding="utf-8") as f:
        processed = segment(f.read(), tok)
    src_dir = os.path.dirname(os.path.abspath(a.src))
    if a.keep:
        tmp = os.path.splitext(a.src)[0] + ".th.typ"
    else:
        fd, tmp = tempfile.mkstemp(suffix=".typ", dir=src_dir)
        os.close(fd)
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(processed)
    cmd = [TYPST, "compile", "--root", src_dir, tmp, a.out]
    if a.out.lower().endswith(".png"):
        cmd += ["--ppi", a.ppi]
    r = subprocess.run(cmd)
    if not a.keep:
        os.remove(tmp)
    sys.exit(r.returncode)


if __name__ == "__main__":
    main()
