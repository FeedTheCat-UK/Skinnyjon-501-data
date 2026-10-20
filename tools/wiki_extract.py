#!/usr/bin/env python3
"""Pull every English Wikipedia page that uses the football biography infobox out of the
multistream dump, without saving the 27 GB dump itself.

  python3 extract.py plan          -> works out 40 byte ranges from the index (chunks.json)
  python3 extract.py run N         -> streams chunk N and writes out/chunk_NN.jsonl.gz
"""
import bz2, gzip, json, os, re, subprocess, sys

URL = 'https://dumps.wikimedia.org/enwiki/latest/enwiki-latest-pages-articles-multistream.xml.bz2'
SIZE = 26917225724
HERE = os.path.dirname(os.path.abspath(__file__))
NCHUNK = 40


def plan():
    offs = set()
    with bz2.open(os.path.join(HERE, 'index.txt.bz2'), 'rt', encoding='utf-8') as f:
        for line in f:
            offs.add(int(line.split(':', 1)[0]))
    offs = sorted(offs)
    step = len(offs) // NCHUNK
    starts = [offs[i * step] for i in range(NCHUNK)]
    chunks = [[s, (starts[i + 1] - 1) if i + 1 < NCHUNK else SIZE - 1] for i, s in enumerate(starts)]
    json.dump(chunks, open(os.path.join(HERE, 'chunks.json'), 'w'))
    print(len(offs), 'streams ->', len(chunks), 'chunks')


TITLE = re.compile(rb'<title>(.*?)</title>')
NS = re.compile(rb'<ns>(\d+)</ns>')


def run(n):
    s, e = json.load(open(os.path.join(HERE, 'chunks.json')))[n]
    os.makedirs(os.path.join(HERE, 'out'), exist_ok=True)
    final = os.path.join(HERE, 'out', 'chunk_%02d.jsonl.gz' % n)
    if os.path.exists(final):
        return
    tmp = final + '.part'
    curl = subprocess.Popen(['curl', '-sSf', '--retry', '8', '--retry-delay', '20', '-r', '%d-%d' % (s, e), URL],
                            stdout=subprocess.PIPE)
    unz = subprocess.Popen(['bzip2', '-dc'], stdin=curl.stdout, stdout=subprocess.PIPE, bufsize=1 << 20)
    curl.stdout.close()
    kept = pages = 0
    buf = None
    with gzip.open(tmp, 'wt', encoding='utf-8') as out:
        for line in unz.stdout:
            if buf is None:
                if b'<page>' in line:
                    buf = [line]
                continue
            buf.append(line)
            if b'</page>' in line:
                pages += 1
                page = b''.join(buf)
                buf = None
                if b'ootball biography' not in page or b'<redirect' in page:
                    continue
                ns = NS.search(page)
                if not ns or ns.group(1) != b'0':
                    continue
                t = TITLE.search(page).group(1).decode('utf-8')
                a = page.find(b'<text')
                a = page.find(b'>', a) + 1
                b = page.rfind(b'</text>')
                import html
                text = html.unescape(page[a:b].decode('utf-8', 'replace'))
                out.write(json.dumps({'t': html.unescape(t), 'x': text}, ensure_ascii=False) + '\n')
                kept += 1
    unz.wait(); curl.wait()
    if curl.returncode != 0 or unz.returncode != 0:
        print('chunk', n, 'FAILED curl', curl.returncode, 'bzip2', unz.returncode, flush=True)
        sys.exit(1)
    os.rename(tmp, final)
    print('chunk', n, 'done', pages, 'pages', kept, 'footballers', flush=True)


if __name__ == '__main__':
    if sys.argv[1] == 'plan':
        plan()
    else:
        run(int(sys.argv[2]))
