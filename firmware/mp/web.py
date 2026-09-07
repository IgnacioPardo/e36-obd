# Panel del E36 servido por el propio ESP32.
#
# Levanta un punto de acceso propio: en el auto no hay red, asi que el auto ES
# la red. El celular se une a "E36-OBD" y abre http://192.168.4.1
#
# Un solo hilo: el servidor HTTP hace la lectura de K-line de forma sincronica.
# Una lectura del bloque central cuesta ~341 ms, asi que la pagina pide de a una
# y no se pisan. Es la misma decision que en el panel de macOS -- ahi tambien
# hay un unico hilo dueno del puerto serie.
#
# Uso:
#     import web
#     web.arrancar()

import socket
import time

import network

import kline

SSID = "E36-OBD"
PASS = "motronic17"          # minimo 8 caracteres

_sesion = False


def ap():
    w = network.WLAN(network.AP_IF)
    w.active(True)
    w.config(essid=SSID, password=PASS, authmode=network.AUTH_WPA_WPA2_PSK)
    while not w.active():
        time.sleep_ms(100)
    return w.ifconfig()[0]


PAGINA = """<!DOCTYPE html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>E36</title><style>
:root{--b:#000;--p:#0b0705;--l:#241608;--i:#ff8551;--i2:#8a4526;--s:#e0521a}
*{box-sizing:border-box}
body{margin:0;background:var(--b);color:var(--i);
 font:14px/1.5 ui-monospace,SFMono-Regular,Menlo,monospace;padding:14px}
h1{font-size:13px;letter-spacing:.2em;margin:0 0 4px;font-weight:600}
.sub{color:var(--i2);font-size:11px;letter-spacing:.14em;margin-bottom:16px}
.g{display:grid;grid-template-columns:1fr 1fr;gap:1px;background:var(--l);
 border:1px solid var(--l);border-radius:3px;overflow:hidden;margin-bottom:14px}
.c{background:var(--p);padding:12px 13px}
.k{font-size:9.5px;letter-spacing:.16em;color:var(--i2);text-transform:uppercase}
.v{font-size:26px;font-variant-numeric:tabular-nums;margin-top:3px}
.v small{font-size:11px;color:var(--i2);margin-left:3px}
button{background:var(--p);color:var(--i);border:1px solid var(--l);
 border-radius:3px;padding:13px;font:600 12px ui-monospace;letter-spacing:.12em;
 width:100%;margin-bottom:8px;-webkit-appearance:none}
button:active{background:var(--l)}
button.on{border-color:var(--s);color:var(--s)}
pre{background:var(--p);border:1px solid var(--l);border-radius:3px;
 padding:11px;font-size:11px;white-space:pre-wrap;color:var(--i2);
 max-height:44vh;overflow:auto;margin:0}
.st{font-size:11px;color:var(--i2);margin:10px 0;min-height:16px}
</style></head><body>
<h1>E36 &middot; MOTRONIC 1.7.2</h1>
<div class="sub">M43B16 &middot; 1994 &middot; KWP71 @ 0x10</div>

<div class="g">
 <div class="c"><div class="k">Regimen</div><div class="v" id="rpm">&mdash;<small>rpm</small></div></div>
 <div class="c"><div class="k">Carga</div><div class="v" id="carga">&mdash;<small>ms</small></div></div>
 <div class="c"><div class="k">Refrigerante</div><div class="v" id="refrig">&mdash;<small>&deg;C</small></div></div>
 <div class="c"><div class="k">Bateria</div><div class="v" id="bat">&mdash;<small>V</small></div></div>
</div>

<button id="bl" onclick="live()">EN VIVO</button>
<button onclick="fallas()">LEER FALLAS</button>
<div class="st" id="st">sin sesion</div>
<pre id="log">Toca EN VIVO o LEER FALLAS.

La primera vez abre la sesion: 2,6 s de bus
en reposo mas 2 s de init de 5 baudios.
El motor tiene que estar en marcha para que
los sensores den algo distinto de cero.</pre>

<script>
let on=false,hz=[];
const $=i=>document.getElementById(i);
function st(t){$('st').textContent=t}
function log(t){$('log').textContent=t}
async function tick(){
 if(!on)return;
 const t0=Date.now();
 try{
  const r=await fetch('/d');const d=await r.json();
  if(d.error){st('error: '+d.error);on=false;$('bl').className='';return}
  $('rpm').innerHTML=d.rpm+'<small>rpm</small>';
  $('carga').innerHTML=d.carga+'<small>ms</small>';
  $('refrig').innerHTML=d.refrig+'<small>&deg;C</small>';
  $('bat').innerHTML=d.bateria+'<small>V</small>';
  hz.push(Date.now()-t0);if(hz.length>8)hz.shift();
  const m=hz.reduce((a,b)=>a+b,0)/hz.length;
  st('en vivo &middot; '+m.toFixed(0)+' ms &middot; '+(1000/m).toFixed(2)+' Hz');
  $('st').innerHTML='en vivo &middot; '+m.toFixed(0)+' ms &middot; '+(1000/m).toFixed(2)+' Hz';
  log('crudo  '+d.crudo);
 }catch(e){st('se corto: '+e);on=false;$('bl').className='';return}
 setTimeout(tick,60);
}
function live(){on=!on;$('bl').className=on?'on':'';if(on){st('abriendo sesion...');tick()}else st('detenido')}
async function fallas(){
 on=false;$('bl').className='';st('leyendo memoria de fallas...');
 try{const r=await fetch('/f');const d=await r.json();
  st(d.error?('error: '+d.error):'listo');log(d.texto||d.error)}
 catch(e){st('se corto: '+e)}
}
</script></body></html>"""


def _sesion_lista():
    global _sesion
    if _sesion:
        return
    kline.conectar(verbose=False)
    _sesion = True


def _json(d):
    partes = []
    for k, v in d.items():
        if isinstance(v, str):
            partes.append('"%s":"%s"' % (k, v.replace('"', "'")))
        else:
            partes.append('"%s":%s' % (k, v))
    return "{" + ",".join(partes) + "}"


def _datos():
    global _sesion
    try:
        _sesion_lista()
        return _json(kline.leer_core())
    except Exception as e:
        _sesion = False
        return _json({"error": str(e)})


def _fallas():
    global _sesion
    try:
        _sesion = False                    # las fallas piden sesion fresca
        kline.conectar(verbose=False)
        lineas = []
        for blk in kline.command(kline.READ_FAULTS):
            for i in range(0, len(blk) - 4, 5):
                cod, cond, rpm, b3, frec = blk[i:i + 5]
                lineas.append("codigo %3d  cond 0x%02X  ocurrencias %d"
                              % (cod, cond, frec))
                if cod in kline.NOMBRES:
                    lineas.append("    %s" % kline.NOMBRES[cod])
        _sesion = True
        return _json({"texto": "\\n".join(lineas) or "sin fallas almacenadas"})
    except Exception as e:
        _sesion = False
        return _json({"error": str(e)})


def arrancar(puerto=80):
    """AP + servidor, todo junto. Para usar desde el REPL."""
    ip = ap()
    print()
    print("=== panel del E36 ===")
    print("  red      %s" % SSID)
    print("  clave    %s" % PASS)
    print("  abrir    http://%s" % ip)
    print()
    servir(puerto)


def servir(puerto=80):
    """Solo el bucle del socket. El AP se levanta aparte, desde el hilo
    principal: configurarlo recien encendido desde un hilo secundario falla
    porque la red todavia no esta inicializada."""
    s = socket.socket()
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind(("0.0.0.0", puerto))
    s.listen(2)

    while True:
        try:
            cl, addr = s.accept()
            cl.settimeout(6)
            pedido = cl.readline() or b""
            while True:                       # descartar cabeceras
                l = cl.readline()
                if not l or l == b"\r\n":
                    break
            ruta = pedido.split(b" ")[1].decode() if b" " in pedido else "/"

            if ruta.startswith("/d"):
                cuerpo, tipo = _datos(), "application/json"
            elif ruta.startswith("/f"):
                cuerpo, tipo = _fallas(), "application/json"
            else:
                cuerpo, tipo = PAGINA, "text/html; charset=utf-8"

            cl.write("HTTP/1.0 200 OK\r\nContent-Type: %s\r\n"
                     "Cache-Control: no-store\r\n\r\n" % tipo)
            cl.write(cuerpo)
            cl.close()
        except Exception as e:
            print("cliente:", e)
            try:
                cl.close()
            except Exception:
                pass
