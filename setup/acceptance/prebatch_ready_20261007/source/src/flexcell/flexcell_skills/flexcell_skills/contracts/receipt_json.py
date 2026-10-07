"""Strict receipt parsing and exact typed value comparison; no ROS dependency."""
import json
import math


def loads(raw):
    def pairs(items):
        result={}
        for key,value in items:
            if key in result:raise ValueError('duplicate receipt key: '+key)
            result[key]=value
        return result
    def number(value):
        result=float(value)
        if not math.isfinite(result):raise ValueError('nonfinite receipt number')
        return result
    def invalid(value):raise ValueError('nonfinite receipt constant: '+value)
    return json.loads(raw,object_pairs_hook=pairs,parse_float=number,parse_constant=invalid)


def same_typed(left,right):
    """Do not let Python False == 0 hide a changed persisted terminal."""
    def encoded(value):return json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False)
    return encoded(left)==encoded(right)
