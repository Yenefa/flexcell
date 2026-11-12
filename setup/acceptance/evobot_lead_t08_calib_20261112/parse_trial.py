import json,sys,os
d=sys.argv[1]
try:
    r=json.load(open(os.path.join(d,'trial','recovery.json')))
    v=r.get('verdict') or r
    print('%.4f' % float(v.get('achieved_m',-1.0)), v.get('attempts','?'), v.get('outcome','?'))
except Exception as e:
    print('- - -')