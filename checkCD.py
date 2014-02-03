import subprocess
import urllib
import json

cdrecordpath =  '/cygdrive/c/Program Files (x86)/cdrtools/cdrecord.exe'

x = subprocess.check_output([cdrecordpath, "dev=1,0,0", "-toc"])
# now has string that is returned.  
#   we should check to make sure it is really got the right device and such...
#   but assuming it is right...                                                

lines = x.split('\n')
tracks = []
for l in lines:
    if l.startswith('track'):
        tracks.append(l[16:26].strip())

if tracks == []:
    print "no track listings in", x
else:
    url = 'http://10.30.67.112:5000/lookupCD?'+urllib.urlencode({'sectors':' '.join(tracks)})
    print url

    f = urllib.urlopen(url)
    obj = f.read()
    print obj

