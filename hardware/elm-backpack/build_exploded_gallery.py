"""Compose print-resolution exploded plates and a four-view contact sheet."""
import hashlib
import json
import math
from pathlib import Path
import zipfile
from PIL import Image,ImageDraw,ImageFont
HERE=Path(__file__).resolve().parent
OUT=HERE/'exports'/'exploded-views'
FONT='/System/Library/Fonts/Supplemental/Arial.ttf'
BOLD='/System/Library/Fonts/Supplemental/Arial Bold.ttf'
INK='#263940';MUTED='#64757d';RULE='#86989f'
font=lambda n,b=False:ImageFont.truetype(BOLD if b else FONT,n)
NAMES=['assembly','reverse','underside','mounts']
FOOTERS={
 'assembly':'Complete boards stay together. Straps and wiring omitted for clarity.',
 'reverse':'OBD plug at left. Buck keepers and underside lid screws lift separately.',
 'underside':'Lid shifted sideways for visibility. Electronics, pads and ELM omitted.',
 'mounts':'Boards shifted outward to expose the seats, wire entry and floor slots.',
}
def dot(a,b):return sum(x*y for x,y in zip(a,b))
def sub(a,b):return tuple(x-y for x,y in zip(a,b))
def unit(a):return tuple(x/math.sqrt(dot(a,a)) for x in a)
def cross(a,b):return (a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0])
def project(point,meta):
    f=unit(sub(meta['target'],meta['camera']));r=unit(cross(f,(0,0,1)));u=cross(r,f)
    q=sub(point,meta['target']);scale=meta['scale']
    return (round((.5+dot(q,r)/scale)*2400),round((.5-dot(q,u)/(scale/1.2))*2000)+190)
scene_hash=hashlib.sha256((HERE/'exports/scene.json').read_bytes()).hexdigest()
for i,name in enumerate(NAMES):
    raw=OUT/(name+'-raw.png')
    if not raw.exists():continue
    m=json.loads((OUT/(name+'.json')).read_text());assert m['source_scene_sha256']==scene_hash
    im=Image.open(raw).convert('RGBA');assert im.size==(2400,2000)
    # No clipping of parts or assembly guides at the source-frame boundary.
    bbox=im.getchannel('A').getbbox();assert bbox and bbox[0]>20 and bbox[1]>20 and bbox[2]<2380 and bbox[3]<1980,(name,bbox)
    plate=Image.new('RGB',(2400,2320),'#e8edef');d=ImageDraw.Draw(plate)
    d.text((90,45),f'E36 / REV E                         {i+1:02d}',font=font(24,True),fill=MUTED)
    d.text((90,86),m['title'],font=font(57,True),fill=INK)
    d.text((90,155),m['subtitle'],font=font(25),fill=MUTED)
    plate.paste(im,(0,190),im)
    if name=='assembly':
        labels=[
          ('BMW ribbed lid',(.024,-.078,.1154),'left'),
          ('Buck converter',(.01375,-.060,.0444),'left'),
          ('Original ELM housing',(.025,-.078,-.101),'left'),
          ('ESP32-S3',(.014,.074,.0454),'right'),
          ('Printed base',(.024,.080,.020),'right'),
          ('M3 × 25 lid screws',(.019,.0756,-.037),'right'),
        ]
        for label,point,side in labels:
            x,y=project(point,m)
            if side=='left':
                tx=90;line_start=410
                d.line([(line_start,y),(x-22,y),(x,y)],fill=RULE,width=2)
            else:
                tx=1950;line_start=1920
                d.line([(x,y),(x+22,y),(line_start,y)],fill=RULE,width=2)
            d.ellipse((x-5,y-5,x+5,y+5),fill=RULE)
            d.text((tx,y-37),label,font=font(26),fill=INK)
    d.line((90,2200,2310,2200),fill='#bfccd1',width=2)
    d.text((90,2225),FOOTERS[name],font=font(27),fill=INK)
    d.text((90,2275),'Actual CAD geometry · Display separation only · Assembled case 162 × 48 × 30.4 mm',font=font(23),fill=MUTED)
    plate.save(OUT/(name+'.png'),dpi=(300,300))
    print('Composed',name,'source bounds',bbox)
if all((OUT/(n+'.png')).exists() for n in NAMES):
    sheet=Image.new('RGB',(3200,3260),'#e8edef');d=ImageDraw.Draw(sheet)
    d.text((70,40),'E36 / EXPLODED VIEWS',font=font(58,True),fill=INK)
    d.text((70,115),'Inline adapter · Black casing / BMW ribs · Revision E',font=font(29),fill=MUTED)
    for i,name in enumerate(NAMES):
        im=Image.open(OUT/(name+'.png'));im=im.resize((1500,1450),Image.Resampling.LANCZOS)
        sheet.paste(im,(65+(i%2)*1570,220+(i//2)*1500))
    sheet.save(OUT/'all-views.png',dpi=(300,300))
    readme='''# E36 inline adapter — exploded views

Four high-resolution PNG plates generated from the approved revision E CAD:

1. assembly.png — labelled assembly overview
2. reverse.png — OBD-end three-quarter view
3. underside.png — hidden lid screws and bottom of the case
4. mounts.png — board retention and floor features

all-views.png combines all four. Files ending in -raw.png have transparent backgrounds for reuse. The per-view JSON files record the camera and source-geometry hash.

The boards remain complete assemblies. Straps and illustrative wiring are hidden for clarity; the underside view also hides the electronics and ELM. The lid is offset sideways in that view, and the board-mount view spreads the complete boards apart to reveal the seats. All offsets are for display only; the printable model is unchanged. Physical board fit remains provisional.
'''
    (OUT/'README.md').write_text(readme)
    archive=HERE/'elm-backpack-exploded-views.zip'
    files=sorted(f for f in OUT.iterdir() if f.is_file())
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
        for f in files:z.write(f,'e36-exploded-views/'+f.name)
    with zipfile.ZipFile(archive) as z:
        assert z.testzip() is None
        for f in files:assert hashlib.sha256(f.read_bytes()).digest()==hashlib.sha256(z.read('e36-exploded-views/'+f.name)).digest()
    print('Verified',archive.name,archive.stat().st_size,'bytes')
