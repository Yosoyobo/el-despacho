"""El Envoltorio — la app Android (TWA) de El Taller y su huella en El Portero.

La TWA abre SIN barra de URL sólo si `/.well-known/assetlinks.json` publica la
huella SHA-256 del certificado con el que se firmó el APK. Estos candados cuidan
que la huella real no vuelva a ser un placeholder, que el Caddyfile y el
`twa-manifest.json` digan lo mismo, y que la llave nunca entre al repo.
"""

import json
import re
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
PAQUETE = "mx.learningcenter.taller"
HUELLA_SHA256 = re.compile(r"^(?:[0-9A-F]{2}:){31}[0-9A-F]{2}$")


def _assetlinks_del_caddyfile() -> list:
    texto = (RAIZ / "Caddyfile").read_text(encoding="utf-8")
    m = re.search(
        r"handle /\.well-known/assetlinks\.json \{.*?respond `(.*?)` 200",
        texto,
        re.S,
    )
    assert m, "El bloque de taller debe servir /.well-known/assetlinks.json"
    return json.loads(m.group(1))


def _twa_manifest() -> dict:
    return json.loads((RAIZ / "envoltorio" / "twa-manifest.json").read_text(encoding="utf-8"))


class TestHuellaEnElPortero:
    def test_ya_no_hay_placeholder(self):
        texto = (RAIZ / "Caddyfile").read_text(encoding="utf-8")
        assert "REEMPLAZAR_CON_FINGERPRINT_SHA256" not in texto

    def test_assetlinks_es_json_valido_con_la_relacion_correcta(self):
        declaraciones = _assetlinks_del_caddyfile()
        assert isinstance(declaraciones, list) and len(declaraciones) == 1
        d = declaraciones[0]
        assert d["relation"] == ["delegate_permission/common.handle_all_urls"]
        assert d["target"]["namespace"] == "android_app"
        assert d["target"]["package_name"] == PAQUETE

    def test_la_huella_tiene_formato_sha256(self):
        huellas = _assetlinks_del_caddyfile()[0]["target"]["sha256_cert_fingerprints"]
        assert huellas, "Sin huella la app abre con barra de URL"
        for h in huellas:
            assert HUELLA_SHA256.match(h), f"Huella con formato inválido: {h!r}"

    def test_caddyfile_y_twa_manifest_dicen_la_misma_huella(self):
        del_portero = set(_assetlinks_del_caddyfile()[0]["target"]["sha256_cert_fingerprints"])
        del_manifest = {f["value"] for f in _twa_manifest()["fingerprints"]}
        assert del_portero == del_manifest


class TestTwaManifest:
    def test_paquete_host_y_nombre(self):
        m = _twa_manifest()
        assert m["packageId"] == PAQUETE
        assert m["host"] == "taller.learningcenter.mx"
        assert m["launcherName"] == "El Taller"
        assert m["signingKey"]["alias"] == "taller"

    def test_sin_secretos_ni_rutas_absolutas(self):
        crudo = (RAIZ / "envoltorio" / "twa-manifest.json").read_text(encoding="utf-8")
        for prohibido in ("/Users/", "/Volumes/", "/private/", "~/", "password", "Password"):
            assert prohibido not in crudo, f"twa-manifest.json no debe llevar {prohibido!r}"
        ruta = _twa_manifest()["signingKey"]["path"]
        assert not ruta.startswith("/"), "La ruta de la llave va relativa (se pasa --signingKeyPath al build)"

    def test_el_color_es_el_de_la_pwa(self):
        pwa = json.loads((RAIZ / "el-taller" / "static" / "manifest.json").read_text(encoding="utf-8"))
        assert _twa_manifest()["themeColor"].lower() == pwa["theme_color"].lower()


class TestManifestPwaAlcanzaParaBubblewrap:
    def test_campos_que_pide_bubblewrap(self):
        m = json.loads((RAIZ / "el-taller" / "static" / "manifest.json").read_text(encoding="utf-8"))
        for campo in ("name", "short_name", "start_url"):
            assert m.get(campo), f"manifest sin {campo}"
        assert m["display"] == "standalone"
        iconos = m["icons"]
        assert any(i["sizes"] == "512x512" and i.get("purpose", "any") == "any" for i in iconos)
        assert any(i["sizes"] == "512x512" and "maskable" in i.get("purpose", "") for i in iconos)
        for i in iconos:
            ruta = RAIZ / "el-taller" / i["src"].lstrip("/")
            assert ruta.exists(), f"Ícono del manifest inexistente: {i['src']}"


class TestLaLlaveNuncaAlRepo:
    def test_gitignore_excluye_llaves_y_builds(self):
        reglas = (RAIZ / ".gitignore").read_text(encoding="utf-8").splitlines()
        for patron in ("*.keystore", "*.jks", "*.apk", "*.aab", "envoltorio/app/"):
            assert patron in reglas, f".gitignore debe excluir {patron}"
