"""Build the offline CAD viewer, inline layout drawing and actual-mesh previews."""
import json
from html import escape
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
OUT = HERE / 'exports'
scene = json.loads((OUT / 'scene.json').read_text())
p = scene['parameters']
W,L,H,F,LT = (p[k] for k in ('case_width','case_length','base_height','floor','lid_thickness'))
size = f'{L:g} × {W:g} × {H+LT:g}'
wire_size = f"{p['wire_entry_width']:g} × {p['wire_entry_length']:g}"
template = (HERE/'viewer.html.in').read_text()
template = template.replace('__CASE_SIZE__',size).replace('__WIRE_SIZE__',wire_size)
(HERE/'viewer.html').write_text(template.replace('__SCENE_DATA__',(OUT/'scene.json').read_text()))

svg = ['''<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="1080" viewBox="0 0 1200 1080"><defs><marker id="a" viewBox="0 0 8 8" refX="4" refY="4" markerWidth="5" markerHeight="5" orient="auto-start-reverse"><path d="M0 0L8 4L0 8" fill="none" stroke="#557482"/></marker></defs><style>text{font-family:Arial,sans-serif}.dim{stroke:#557482;stroke-width:1;marker-start:url(#a);marker-end:url(#a)}.lead{fill:none;stroke:#8399a3;stroke-width:1.2}</style><rect width="1200" height="1080" fill="#f4f7f8"/>''']
def text(x,y,s,size=14,color='#253e4c',bold=False):
    svg.append(f'<text x="{x}" y="{y}" font-size="{size}" fill="{color}" font-weight="{"bold" if bold else "normal"}">{escape(s)}</text>')
def rect(x,y,w,h,fill,stroke='#537081',r=2):
    svg.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{r}" fill="{fill}" stroke="{stroke}" stroke-width="1.3"/>')
def plan_box(x,y,w,l,color):
    rect(600+5*(y-l/2),300+5*(x-w/2),5*l,5*w,color)
def dim(x1,y1,x2,y2,label,tx,ty):
    svg.append(f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" class="dim"/>');text(tx,ty,label,15)
def lead(points,label,x,y):
    svg.append(f'<polyline points="{points}" class="lead"/>');text(x,y,label,13)
text(52,50,'E36 / HARDWARE · REV E',12,bold=True)
text(52,88,'Inline ECU adapter · 48 mm narrow body',29,bold=True)
text(52,115,'All dimensions in mm. Nominal references; physical fit check required. Not a 1:1 paper template.',13,'#6c7f88')
text(195,154,'TOP · LID REMOVED · OBD END AT LEFT',14,bold=True)
plan_box(0,0,W,L,'#d8e2e8');plan_box(0,0,W-2*p['wall'],L-2*p['wall'],'#edf2f4')
for y in p['strap_y']+[p['rear_anchor_y']]:
    plan_box(0,y,39.6,12,'#cad3d8')
    for x in (-p['strap_slot_x'],p['strap_slot_x']):plan_box(x,y,2.4,12,'#475961')
for name,color in (('buck','#9cbbcf'),('esp','#afc7be')):
    x,y,w,l=(p[f'{name}_{k}'] for k in ('x','y','width','length'))
    plan_box(x,y,w,l,color)
    text(600+5*y-34,294,'BUCK' if name=='buck' else 'ESP32-S3',13,bold=True)
    text(600+5*y-34,315,f'{l:g} × {w:g}',12)
plan_box(p['wire_entry_x'],p['wire_entry_y'],p['wire_entry_width'],p['wire_entry_length'],'#fff')
plan_box(p['wire_anchor_x'],p['wire_anchor_y'],6,6,'#b4c2cb')
for side in (-1,1):
    for off in (-p['buck_clamp_fraction'],p['buck_clamp_fraction']):
        plan_box(side*(p['buck_width']/2+3.7),p['buck_y']+off*p['buck_length'],6.4,6.4,'#e7a479')
antenna_y=p['esp_y']-p['esp_length']/2+p['esp_antenna_overhang']/2
plan_box(0,antenna_y,18,p['esp_antenna_overhang'],'#71998a')
plan_box(0,L/2,32,1.2,'#253e4c')
for x in (-W/2+5,W/2-5):
    for y in (-L/2+5.4,L/2-5.4):plan_box(x,y,5.6,5.6,'#8297a2')
dim(160,300-2.5*W,160,300+2.5*W,f'{W:g}',127,306)
dim(600-2.5*L,455,600+2.5*L,455,f'{L:g}',586,479)
lead('630,238 630,165 660,165',f'{wire_size} floor entry',668,168)
lead('1008,300 1040,300 1040,274','REAR USB',1023,256)
text(195,502,'Two recessed straps below buck',13)
text(700,502,'Rear support-tie position below ESP',13)
text(195,548,'LONGITUDINAL SECTION · SCHEMATIC COMPONENT ENVELOPES',14,bold=True)
zbase=725
rect(600-L*2.5,zbase-H*5,L*5,H*5,'#d8e2e8')
rect(600-L*2.5+p['wall']*5,zbase-H*5,(L-2*p['wall'])*5,(H-F)*5,'#f4f7f8','#f4f7f8',0)
rect(600-L*2.5,zbase-(H+LT)*5,L*5,LT*5,'#657e8a')
for name,fill in (('buck','#7da5be'),('esp','#90b6a6')):
    y,length=p[name+'_y'],p[name+'_length'];z=F+p[name+'_under_board']
    xx=600+5*(y-length/2)
    rect(xx,zbase-(z+p['pcb_thickness'])*5,length*5,p['pcb_thickness']*5,fill)
    rect(xx+10,zbase-(z+p['pcb_thickness']+p[name+'_top_allowance'])*5,
         length*5-20,p[name+'_top_allowance']*5,'#dce5e9','#8fa5af')
    text(xx+24,zbase-(z+p['pcb_thickness'])*5-12,name.upper(),12)
for y in p['strap_y']+[p['rear_anchor_y']]:
    rect(600+5*(y-6),zbase-F*5,60,5,'#f4f7f8','#f4f7f8',0)
    if y in p['strap_y']:rect(600+5*(y-5),zbase-F*5,50,5,'#454d51','#454d51',0)
elmstart=-L/2;elml=p['elm_body_length_reference'];ep=p['mounting_pad_thickness'];eh=p['elm_body_height_reference']
rect(600+5*elmstart,zbase+ep*5,elml*5,eh*5,'#39454b')
rect(600+5*(elmstart-20),zbase+(ep+5)*5,100,80,'#202b32')
text(283,810,'ELM REFERENCE · UNMEASURED',12,'#fff',True)
for y in p['mount_pad_y']:rect(600+5*(y-8),zbase,80,ep*5,'#97a2a7')
dim(1040,zbase-(H+LT)*5,1040,zbase,f'{H+LT:g}',1053,659)
text(1046,706,'case only',11)
lead('630,740 650,778 695,778','Wire entry beyond ELM tail',704,782)
lead('870,729 870,829 900,829','Support the extended tail',911,834)
text(195,902,'Buck: 4 below PCB / 18 above / 2 roof clearance',13)
text(195,925,'ESP: 5 below PCB / 1.5 solder joints / 3.5 for wires / 14 roof clearance',13)
text(195,948,'2.4 walls and floor; floor is 1.4 locally under 1 mm mounting straps. Lid field: 2.0 minimum.',13)
svg.append('<line x1="52" y1="984" x2="1148" y2="984" stroke="#c6d3d9"/>')
text(52,1015,'Print 1 base + 1 lid + 4 keepers. Lid fastens from below with M3 × 25 screws; top has no fasteners.',13)
text(52,1041,'Rear USB roof requires local removable support. Board dimensions and available vehicle space need a physical check.',13,'#6c7f88')
svg.append('</svg>');(OUT/'dimensions.svg').write_text(''.join(svg))

font_path='/System/Library/Fonts/Supplemental/Arial.ttf'
large,medium,small=[ImageFont.truetype(font_path,n) for n in (48,31,24)]
if all((OUT/(n+'.png')).exists() for n in ('assembled','interior','exploded')):
    sheet=Image.new('RGB',(2400,1120),'#e9eef0');d=ImageDraw.Draw(sheet)
    d.text((60,42),'INLINE ECU ADAPTER / REV E',font=large,fill='#243947')
    d.text((60,107),f'{size} mm · Direct solder · Rear USB · FIT CHECK REQUIRED',font=small,fill='#6a7d87')
    for i,(name,label) in enumerate((('assembled','01 / Clear top · BMW ribs'),('interior','02 / Boards end-to-end'),('exploded','03 / Screws from underneath'))):
        im=Image.open(OUT/(name+'.png')).convert('RGB');im.thumbnail((760,760))
        sheet.paste(im,(30+i*790+(760-im.width)//2,225))
        d.text((60+i*790,168),label,font=medium,fill='#243947')
    d.text((60,1017),'41% narrower body. Mounting straps run below the boards; the long lid stays uninterrupted.',font=small,fill='#465f6c')
    d.text((60,1058),'Black print with optional silver rib and BMW paint. Actual CAD meshes; physical fit and vehicle clearance remain provisional.',font=small,fill='#6a7d87')
    sheet.save(OUT/'preview.png')
if (OUT/'previous-d.png').exists() and (OUT/'assembled.png').exists():
    sheet=Image.new('RGB',(2400,1390),'#e9eef0');d=ImageDraw.Draw(sheet)
    d.text((60,42),'E36 / INLINE REDESIGN',font=large,fill='#243947')
    d.text((60,115),'Previous / 110 × 82 mm',font=medium,fill='#5b6c74')
    d.text((1250,115),'Current / 162 × 48 mm',font=medium,fill='#243947')
    # Use the rendered camera scales to keep the comparison at equal nominal scale.
    for name,x,scale in (('previous-d',25,.198),('assembled',1225,.215)):
        im=Image.open(OUT/(name+'.png')).convert('RGB')
        width=round(1130*scale/.215);im=im.resize((width,round(width*im.height/im.width)))
        sheet.paste(im,(x+(1150-im.width)//2,210+(1000-im.height)//2))
    d.text((60,1250),'Wide body / straps crossing the lid',font=medium,fill='#5b6c74')
    d.text((1250,1250),'Narrow inline body / hidden mounting',font=medium,fill='#243947')
    d.text((60,1320),'Actual CAD renders at the same nominal scale; different view angles. Same 30.4 mm case height.',font=small,fill='#6a7d87')
    sheet.save(OUT/'comparison.png')
print('Built viewer, inline dimensions, preview and comparison.')
