#!/usr/bin/env python3
"""
Actualiza datos-mercado.json leyendo las fuentes oficiales.

Todo lo que publica el cartel se trae solo:
  - Escrituras de compraventa en CABA, hipotecas y monto medio por operacion:
    del post mensual del Colegio de Escribanos.
  - Variacion del m2 CABA: del indice M2 Real (REMAX + UCEMA), que publica el
    porcentaje en el HTML de su pagina.

El valor en US$/m2 y la brecha entre precio publicado y de cierre salen del PDF
del informe, de la pagina titulada "PRECIOS GENERALIZADOS DE DEPARTAMENTOS CABA":
es la unica tabla con los meses rotulados, asi que se puede ubicar sin ambiguedad.

Si una fuente falla, se conserva el valor anterior. Nunca deja el archivo vacio.
"""
import json, re, sys, urllib.request, datetime, pathlib, logging

# pypdf avisa por cada fuente Gotham del informe; es ruido, no afecta la lectura
logging.getLogger("pypdf").setLevel(logging.ERROR)

RAIZ = pathlib.Path(__file__).resolve().parent.parent
ARCHIVO = RAIZ / "datos-mercado.json"
UA = {"User-Agent": "Mozilla/5.0 (compatible; llamaloafer-bot/1.0; +https://llamaloafer.com.ar)"}
MESES = ["enero","febrero","marzo","abril","mayo","junio",
         "julio","agosto","septiembre","octubre","noviembre","diciembre"]
ABREV = {m: m[:3] for m in MESES}


def bajar(url, timeout=45):
    req = urllib.request.Request(url, headers=UA)
    return urllib.request.urlopen(req, timeout=timeout).read().decode("utf-8", "ignore")


def sin_tags(html):
    t = re.sub(r"<script.*?</script>", " ", html, flags=re.S | re.I)
    t = re.sub(r"<style.*?</style>", " ", t, flags=re.S | re.I)
    t = re.sub(r"<[^>]+>", " ", t)
    t = t.replace("&nbsp;", " ").replace("&#8220;", '"').replace("&#8221;", '"')
    return re.sub(r"\s+", " ", t)


def escrituras():
    """Ultimo informe mensual del Colegio de Escribanos: trae los tres numeros."""
    cat = bajar("https://www.colegio-escribanos.org.ar/category/estadisticas-de-escrituras/")
    posts = re.findall(
        r'href="(https://www\.colegio-escribanos\.org\.ar/(\d{4})/(\d{2})/(\d{2})/cantidad-de-escrituras[^"]*)"',
        cat)
    if not posts:
        raise RuntimeError("no encontre posts de escrituras")
    url = sorted(set(posts), key=lambda p: (p[1], p[2], p[3]), reverse=True)[0][0]
    txt = sin_tags(bajar(url))

    out = {"url": url}

    slug = url.rstrip("/").split("/")[-1]
    mm = re.search(r"realizadas-en-([a-zñ]+)-(\d{4})", slug)
    out["periodo"] = "%s %s" % (ABREV[mm.group(1)], mm.group(2)) if mm and mm.group(1) in ABREV else ""

    m = re.search(r"\b(\d{1,2}\.\d{3})\s+escrituras", txt)
    if not m:
        raise RuntimeError("no encontre la cantidad de escrituras")
    out["escrituras"] = m.group(1)

    v = re.search(r"(ca[ií]d\w+|baja|descens\w+|aument\w+|sub\w+|crecimient\w+)[^.]{0,80}?(\d{1,2},\d)\s*%", txt, re.I)
    if v:
        n = float(v.group(2).replace(",", "."))
        out["escrituras_delta"] = -n if re.match(r"ca[ií]|baj|descens", v.group(1), re.I) else n

    # "El monto medio ... fue de $X ( 119.270 dolares ...): crecio 10,3% ... bajo un 2,7%"
    md = re.search(r"monto medio[\s\S]{0,170}?\(\s*([\d.]+)\s*d[oó]lares", txt, re.I)
    if md:
        out["monto"] = "US$ " + md.group(1)
        mv = re.search(r"moneda estadounidense\s+(baj\w+|subi\w+|creci\w+|aument\w+)[\s\S]{0,40}?(\d{1,2},\d)\s*%", txt, re.I)
        if mv:
            n = float(mv.group(2).replace(",", "."))
            out["monto_delta"] = -n if re.match(r"baj", mv.group(1), re.I) else n

    # "hubo 1059 escrituras formalizadas con hipoteca ... la baja ... es del 20,8%"
    hp = re.search(r"(\d{1,2}[.]?\d{3})\s+escrituras\s+formalizadas\s+con\s+hipoteca", txt, re.I)
    if hp:
        n = hp.group(1)
        out["hipotecas"] = n if "." in n else "{:,}".format(int(n)).replace(",", ".")
        hv = re.search(r"con hipoteca[\s\S]{0,180}?(baja|suba|aument\w+|ca[ií]d\w+)[\s\S]{0,50}?(\d{1,2},\d)\s*%", txt, re.I)
        if hv:
            n2 = float(hv.group(2).replace(",", "."))
            out["hipotecas_delta"] = -n2 if re.match(r"baj|ca[ií]", hv.group(1), re.I) else n2

    return out


ULTIMO_INFORME = "https://ucema.edu.ar/novedad/ultimo-informe-indice-metro-cuadrado-real"


def m2():
    """Indice M2 Real (REMAX + UCEMA).

    Arranca de la pagina de "ultimo informe", que es fija y siempre apunta al
    PDF mas nuevo: asi no hay que adivinar el mes. Del PDF salen el valor en
    US$/m2 y la brecha contra el precio publicado, de la pagina titulada
    "PRECIOS GENERALIZADOS DE DEPARTAMENTOS CABA" (la unica con los meses
    rotulados; las demas son cortes por barrio o tipologia). La variacion
    mensual se toma de la pagina del mes, que la publica en el HTML.
    """
    portada = bajar(ULTIMO_INFORME)
    m = re.search(r'href="([^"]*Informe_M2[^"]*\.pdf)"', portada, re.I)
    if not m:
        raise RuntimeError("no encontre el PDF en la pagina de ultimo informe")
    pdf_url = m.group(1)
    if pdf_url.startswith("/"):
        pdf_url = "https://ucema.edu.ar" + pdf_url

    # del nombre del archivo sale el mes del informe
    fm = re.search(r"Informe_M2_Real_([A-Za-zÁÉÍÓÚáéíóú]+)_(\d{4})", pdf_url)
    mes_nom = fm.group(1).lower() if fm else ""
    anio = int(fm.group(2)) if fm else datetime.date.today().year
    mes_num = MESES.index(mes_nom) + 1 if mes_nom in MESES else 0
    periodo = "%s %d" % (ABREV.get(mes_nom, mes_nom[:3]), anio)

    from pypdf import PdfReader
    import io as _io
    crudo = urllib.request.urlopen(urllib.request.Request(pdf_url, headers=UA), timeout=60).read()
    lector = PdfReader(_io.BytesIO(crudo))

    valor = brecha = None
    for pag in lector.pages:
        try:
            txt = re.sub(r"\s+", " ", pag.extract_text() or "")
        except Exception:
            continue
        if "GENERALIZADOS DE DEPARTAMENTOS CABA" not in txt.upper():
            continue
        mm = re.search(r"Mes\s+((?:[A-ZÁÉÍÓÚÑ]{4,10}\s*){3,13}?)Valor\s*M2\(USD\)\s*((?:\d{3,4}\s*){3,13})", txt)
        if not mm:
            continue
        meses, valores = mm.group(1).split(), mm.group(2).split()
        n = min(len(meses), len(valores))
        if n < 3:
            continue
        v = int(valores[n - 1])
        if not (900 < v < 5000):          # cordura: un m2 de CABA esta en ese rango
            raise RuntimeError("valor fuera de rango: %s" % v)
        valor = "US$ " + "{:,}".format(v).replace(",", ".")
        mb = re.search(r"Publicado\s*\(%\)\s*((?:-?\d{1,2},\d{1,2}\s*){3,13})", txt)
        if mb:
            br = mb.group(1).split()
            if len(br) >= n:
                brecha = float(br[n - 1].replace(",", "."))
        break

    if valor is None:
        raise RuntimeError("no encontre la tabla de precios generalizados en el PDF")

    # variacion mensual: la publica la pagina del mes
    delta = None
    pagina = ULTIMO_INFORME
    if mes_num:
        pagina = "https://ucema.edu.ar/indices-y-bases-de-datos/m2-%02d%d" % (mes_num, anio)
        try:
            pcts = re.findall(r"(-?\d{1,2},\d{1,2})\s*%", sin_tags(bajar(pagina, timeout=30)))
            if pcts:
                delta = float(pcts[0].replace(",", "."))
        except Exception:
            pagina = ULTIMO_INFORME

    return {"valor": valor, "brecha": brecha, "delta": delta,
            "periodo": periodo, "url": pagina, "pdf": pdf_url}


def main():
    datos = json.loads(ARCHIVO.read_text(encoding="utf-8"))
    por = {it["label"]: it for it in datos["items"]}
    cambios = []

    def set_(label, valor=None, delta=None, periodo=None, url=None):
        it = por.get(label)
        if not it:
            return
        if valor is not None and it.get("valor") != valor:
            cambios.append("%s: %s -> %s" % (label, it.get("valor"), valor))
        if valor is not None:
            it["valor"] = valor
        if delta is not None:
            it["delta"] = delta
        if periodo:
            it["periodo"] = periodo
        if url:
            it["url"] = url

    try:
        e = escrituras()
        set_("Escrituras CABA", e.get("escrituras"), e.get("escrituras_delta"), e["periodo"], e["url"])
        set_("Con hipoteca", e.get("hipotecas"), e.get("hipotecas_delta"), e["periodo"], e["url"])
        set_("Monto medio por operación", e.get("monto"), e.get("monto_delta"), e["periodo"], e["url"])
        print("OK escrituras: %s | hipotecas: %s | monto: %s (%s)" %
              (e.get("escrituras"), e.get("hipotecas"), e.get("monto"), e["periodo"]))
    except Exception as ex:
        print("FALLO escrituras, conservo lo anterior: %s" % ex, file=sys.stderr)

    try:
        m = m2()
        set_("m² CABA · precio de cierre", m["valor"], m["delta"], m["periodo"], m["url"])
        if m["brecha"] is not None:
            signo = "" if m["brecha"] < 0 else "+"
            set_("Se cierra por debajo del publicado",
                 "%s%s%%" % (signo, ("%.2f" % m["brecha"]).replace(".", ",")),
                 None, m["periodo"], m["url"])
        print("OK m2: %s (%s) | variacion %s%% | brecha %s%%" %
              (m["valor"], m["periodo"], m["delta"], m["brecha"]))
    except Exception as ex:
        print("FALLO m2, conservo lo anterior: %s" % ex, file=sys.stderr)

    datos["actualizado"] = datetime.date.today().isoformat()
    ARCHIVO.write_text(json.dumps(datos, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("cambios:", "; ".join(cambios) if cambios else "ninguno")


if __name__ == "__main__":
    main()
