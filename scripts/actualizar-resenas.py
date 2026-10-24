"""Actualiza la cantidad de reseñas de Google de las fichas de Fernando.

Usa la Places API (New). Necesita la variable de entorno GOOGLE_PLACES_API_KEY.
Si la clave no está, el script no hace nada y termina bien: la página sigue
mostrando los números que ya tiene cargados en datos-resenas.json.

La primera vez resuelve el placeId de cada ficha por su nombre y lo guarda en el
JSON, así las corridas siguientes se saltean esa búsqueda (que se cobra aparte).
"""

import json
import os
import pathlib
import sys
import urllib.error
import urllib.request
from datetime import date

RAIZ = pathlib.Path(__file__).resolve().parent.parent
ARCHIVO = RAIZ / "datos-resenas.json"
CLAVE = os.environ.get("GOOGLE_PLACES_API_KEY", "").strip()

BUSCAR = "https://places.googleapis.com/v1/places:searchText"
DETALLE = "https://places.googleapis.com/v1/places/{}"


def pedir(url, campos, cuerpo=None):
    datos = json.dumps(cuerpo).encode() if cuerpo is not None else None
    req = urllib.request.Request(url, data=datos, method="POST" if datos else "GET")
    req.add_header("X-Goog-Api-Key", CLAVE)
    req.add_header("X-Goog-FieldMask", campos)
    if datos:
        req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())


def resolver_place_id(nombre):
    """Busca la ficha por nombre y devuelve su id, o None si no aparece."""
    res = pedir(BUSCAR, "places.id,places.displayName", {"textQuery": nombre, "languageCode": "es"})
    lugares = res.get("places") or []
    return lugares[0]["id"] if lugares else None


def main():
    datos = json.loads(ARCHIVO.read_text(encoding="utf-8"))

    if not CLAVE:
        print("Sin GOOGLE_PLACES_API_KEY: no se toca nada, quedan los números cargados a mano.")
        return 0

    cambio = False
    for ficha in datos["fichas"]:
        try:
            if not ficha.get("placeId"):
                ficha["placeId"] = resolver_place_id(ficha["busqueda"])
                if not ficha["placeId"]:
                    print(f"  {ficha['id']}: Google no devolvió ninguna ficha para ese nombre.")
                    continue
                cambio = True
                print(f"  {ficha['id']}: placeId resuelto y guardado ({ficha['placeId']}).")

            d = pedir(DETALLE.format(ficha["placeId"]), "rating,userRatingCount")
            puntaje = d.get("rating")
            total = d.get("userRatingCount")
            if total is None:
                print(f"  {ficha['id']}: la respuesta vino sin cantidad de reseñas.")
                continue

            if ficha["resenas"] != total or ficha["puntaje"] != puntaje:
                print(f"  {ficha['id']}: {ficha['resenas']} → {total} reseñas, {ficha['puntaje']} → {puntaje}")
                ficha["resenas"] = total
                ficha["puntaje"] = puntaje
                cambio = True
            else:
                print(f"  {ficha['id']}: sin cambios ({total} reseñas).")

        except urllib.error.HTTPError as e:
            # Un error de una ficha no debe tirar abajo la otra ni dejar el JSON a medias.
            print(f"  {ficha['id']}: error {e.code} de Google — {e.read()[:200]!r}", file=sys.stderr)
        except Exception as e:  # noqa: BLE001
            print(f"  {ficha['id']}: {e}", file=sys.stderr)

    if cambio:
        datos["actualizado"] = date.today().isoformat()
        datos["automatico"] = True
        ARCHIVO.write_text(json.dumps(datos, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print("datos-resenas.json actualizado.")
    else:
        print("Nada que actualizar.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
