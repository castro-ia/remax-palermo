# RE/MAX Palermo · Fernando Castro

Landing page personal para reemplazar Beacons en la bio de Instagram.

- **Una sola página**, sin dependencias ni build. Todo el CSS y JS va embebido en `index.html`.
- **Mobile-first**: el tráfico viene de Instagram.
- **Sin backend**: el formulario de tasación arma un mensaje de WhatsApp prellenado. No se guarda ningún dato.

## Editar

Todo está en `index.html`. Lo que más vas a querer tocar:

| Qué | Dónde buscar |
|---|---|
| Teléfono / WhatsApp | `5491150379426` |
| Titular del hero | `<h1>` |
| Estadísticas (260+, 8 años…) | `class="stats-grid"` |
| Videos de YouTube | `data-yt="ID_DEL_VIDEO"` |
| Testimonios | `class="revs"` |
| Premios | `class="aw-list"` |
| Links (IG, YouTube, etc.) | `class="linkgrid"` |

## Publicar cambios

Editás, guardás y:

```bash
git add -A && git commit -m "actualizo la landing" && git push
```

GitHub Pages republica solo en ~1 minuto.

## Dominio propio

Si comprás un dominio (ej. `fernandocastro.ar`), creá un archivo `CNAME` con el dominio
adentro y apuntá el DNS a GitHub Pages. Acordate de actualizar `<link rel="canonical">`,
`robots.txt` y `sitemap.xml`.
