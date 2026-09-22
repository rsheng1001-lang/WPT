"""Minimal reader for uncompressed real LTspice binary RAW files."""
from pathlib import Path
import re
import numpy as np

def read_raw(path):
    b=Path(path).read_bytes()
    marker='Binary:\n'.encode('utf-16le')
    k=b.find(marker)
    if k<0: raise ValueError('Expected UTF-16LE binary RAW')
    header=b[:k].decode('utf-16le')
    n=int(re.search(r'No\. Variables:\s*(\d+)',header)[1])
    count=int(re.search(r'No\. Points:\s*(\d+)',header)[1])
    names=[line.split()[1] for line in header.split('Variables:\n')[1].splitlines() if line.strip()]
    payload=b[k+len(marker):]
    if 'double' in re.search(r'Flags:(.*)',header)[1]:
        a=np.frombuffer(payload,dtype='<f8',count=n*count).reshape(count,n)
        return {name:a[:,i] for i,name in enumerate(names)}
    dtype=np.dtype([('axis','<f8'),('values','<f4',(n-1,))])
    a=np.frombuffer(payload,dtype=dtype,count=count)
    return {name:a['axis'] if i==0 else a['values'][:,i-1] for i,name in enumerate(names)}

if __name__=='__main__':
    import sys
    d=read_raw(sys.argv[1])
    keys=sys.argv[2:] or list(d)
    print('\t'.join(keys))
    for row in zip(*(d[k] for k in keys)): print('\t'.join(f'{x:.9g}' for x in row))
