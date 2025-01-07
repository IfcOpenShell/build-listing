import functools
import itertools
import operator
import re
import sys
from urllib.parse import quote_plus
import natsort
import humanize
from packaging.utils import parse_wheel_filename

PREFIX='https://s3.amazonaws.com/ifcopenshell-builds/'

def _():
    import json
    d = json.load(open(sys.argv[1]))
    for c in d['Contents']:
        k = c['Key']
        if k.endswith('.zip'):
            parts = k[:-4].rsplit('-', 3)
            if len(parts) == 4:
                product, version, hash, os = parts
                
                if product in {'IfcConvert', 'IfcGeomServer'}:
                    pass
                elif re.match(r'^ifcopenshell-python-\d{2,3}u?$', product):
                    pass
                else:
                    continue

                if len(hash) == 7:
                    pass
                else:
                    continue

                if re.match(r'^v\d\.\d\.\d+$', version):
                    pass
                else:
                    continue

                if os in {'macosm164', 'macos64', 'linux64', 'win32', 'win64', 'linux32'}:
                    pass
                else:
                    continue


                yield version, hash, c['LastModified'], product, os, c['Size'], k
        elif k.endswith('.whl'):
            fixed = k.replace('ifcopenshell-python', 'ifcopenshell_python')
            fixed = re.sub(r'(v\d\.\d\.\d)(\-|\+)(\w{7})', 'v0.8.1+\\3', fixed)
            try:
                module_name, version, _, tags = parse_wheel_filename(fixed)
            except:
                continue

            if len(tags) != 1:
                continue

            tag = next(iter(tags))

            if 'wasm' not in tag.platform:
                continue

            abi = re.sub('c|p|y', '', tag.abi)

            yield f'v{version.public}', version.local, c['LastModified'], f'{module_name}-{abi}', 'WASM', c['Size'], k


hashtodate = dict((hash, functools.reduce(min, (t[1] for t in hash_dates))) for hash, hash_dates in itertools.groupby(sorted((a[1],a[2]) for a in _()), key=operator.itemgetter(0)))
data = natsort.natsorted(_(), reverse=True)
for section, subsections in itertools.groupby(data, key=operator.itemgetter(0)):
    print('##', section)

    for hash, rows in itertools.groupby(sorted(subsections, key=lambda t: hashtodate[t[1]], reverse=True), key=operator.itemgetter(1)):
        print('###', hash, '(%s)' % hashtodate[hash])
        rows = list(rows)
        product, os, size = map(lambda vs: natsort.natsorted(set(vs)), zip(*(r[3:6] for r in rows)))
        osh = list(map(lambda s: s[0].upper() + s[1:], map(lambda s: re.sub(r'(32|64)', ' \\1bit', s.replace('m1', ' M1')).replace('os', 'OS'), os)))
        d = dict((r[3:5], (humanize.naturalsize(r[5]), quote_plus(r[6]))) for r in rows)
        print()
        print('item|', '|'.join(osh))
        print('|'.join(['---']*(len(osh) + 1)))
        for p in product:
            print(p, '|', '|'.join(map(lambda t: '[%%s](%s%%s)' % PREFIX % t, (d.get((p, o), ('-', '')) for o in os))))
        print()
