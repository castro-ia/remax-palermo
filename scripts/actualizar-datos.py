#!/usr/bin/env python3
"""
Actualiza datos-mercado.json con las fuentes que se pueden leer de forma confiable.

Que trae automaticamente:
  - Escrituras de compraventa en CABA: del post mensual del Colegio de Escribanos.
  - Variacion del m2 CABA: del indice M2 Real (REMAX + UCEMA), que publica el
    porcentaje en el HTML de su pagina.

Que NO trae y por que:
  - El valor absoluto en US$/m2 vive en un PDF de 30 paginas con decenas de series
    parecidas (por barrio, por tipologia) y sin etiquetas que permitan distinguir
    la general con certeza. Antes que publicar un numero posiblemente equivocado,
    ese campo se mantiene como estaba y se edita a mano.

Si una fuente falla, se conserva el valor anterior. Nunca deja el archivo vacio.
"""
import json, re, sys, urllib.request, datetime, pathlib

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
    """Ultimo informe mensual del Colegio de Escribanos de CABA."""
    cat = bajar("https://www.colegio-escribanos.org.ar/category/estadisticas-de-escrituras/")
    posts = re.findall(
        r'href="(https://www\.colegio-escribanos\.org\.ar/(\d{4})/(\d{2})/(\d{2})/cantidad-de-escrituras[^"]*)"',
        cat)
    if not posts:
        raise RuntimeError("no encontre posts de escrituras")
    url = sorted(set(posts), key=lambda p: (p[1], p[2], p[3]), reverse=True)[0][0]

    txt = sin_tags(bajar(url))
    m = re.search(r"\b(\d{1,2}\.\d{3})\s+escrituras", txt)
    if not m:
        raise RuntimeError("no encontre la cantidad de escrituras")
    cantidad = m.group(1)

    # mes y año del propio slug del post
    slug = url.rstrip("/").split("/")[-1]
    mm = re.search(r"realizadas-en-([a-zñ]+)-(\d{4})", slug)
    periodo = ""
    if mm and mm.group(1) in ABREV:
        periodo = "%s %s" % (ABREV[mm.group(1)], mm.group(2))

    # variacion interanual, con su signo
    delta = None
    v = re.search(r"(ca[ií]d\w+|baja|descens\w+|aument\w+|sub\w+|crecimient\w+)[^.]{0,80}?(\d{1,2},\d)\s*%", txt, re.I)
    if v:
        n = float(v.group(2).replace(",", "."))
        delta = -n if re.match(r"ca[ií]|baj|descens", v.group(1), re.I) else n

    return {"valor": cantidad, "periodo": periodo, "delta": delta, "url": url}


def m2_variacion():
    """Indice M2 Real (REMAX + UCEMA): busca el informe mas reciente publicado."""
    hoy = datetime.date.today()
    for atras in range(0, 7):
        mes = hoy.month - atras
        anio = hoy.year
        while mes <= 0:
            mes += 12
            anio -= 1
        url = "https://ucema.edu.ar/indices-y-bases-de-datos/m2-%02d%d" % (mes, anio)
        try:
            html = bajar(url, timeout=30)
        except Exception:
            continue
        pcts = re.findall(r"(-?\d{1,2},\d{1,2})\s*%", sin_tags(html))
        if not pcts:
            continue
        return {
            "delta": float(pcts[0].replace(",", ".")),
            "periodo": "%s %d" % (ABREV[MESES[mes - 1]], anio),
            "url": url,
        }
    raise RuntimeError("no encontre informe M2 reciente")


def main():
    datos = json.loads(ARCHIVO.read_text(encoding="utf-8"))
    porEtiqueta = {it["label"]: it for it in datos["items"]}
    cambios = []

    try:
        e = escrituras()
        it = porEtiqueta.get("Escrituras CABA")
        if it and (it["valor"] != e["valor"] or it["periodo"] != e["periodo"]):
            cambios.append("escrituras %s -> %s (%s)" % (it["valor"], e["valor"], e["periodo"]))
        if it:
            it["valor"], it["periodo"], it["url"] = e["valor"], e["periodo"], e["url"]
            if e["delta"] is not None:
                it["delta"] = e["delta"]
        print("OK escrituras: %s (%s, %s%%)" % (e["valor"], e["periodo"], e["delta"]))
    except Exception as ex:
        print("FALLO escrituras, conservo lo anterior: %s" % ex, file=sys.stderr)

    try:
        m = m2_variacion()
        it = porEtiqueta.get("m² CABA · precio de cierre")
        if it and it["periodo"] != m["periodo"]:
            cambios.append("m2 periodo %s -> %s" % (it["periodo"], m["periodo"]))
        if it:
            it["delta"], it["periodo"], it["url"] = m["delta"], m["periodo"], m["url"]
        print("OK m2: %s%% (%s)" % (m["delta"], m["periodo"]))
    except Exception as ex:
        print("FALLO m2, conservo lo anterior: %s" % ex, file=sys.stderr)

    datos["actualizado"] = datetime.date.today().isoformat()
    ARCHIVO.write_text(json.dumps(datos, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("cambios:", "; ".join(cambios) if cambios else "ninguno")


if __name__ == "__main__":
    main()
