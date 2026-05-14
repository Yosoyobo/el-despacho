from lib.sanear import sanear_contexto


def test_strips_script_tags():
    s = sanear_contexto("hola <script>alert(1)</script> mundo")
    assert "<script>" not in s
    assert "alert" in s  # texto plano queda, lo que sí va es el tag


def test_strips_iframe():
    s = sanear_contexto('<iframe src="x"></iframe>')
    assert "<iframe" not in s


def test_neutraliza_js_protocol():
    s = sanear_contexto("javascript:alert(1)")
    assert "javascript:" not in s


def test_neutraliza_on_handlers():
    s = sanear_contexto('<div onclick="x">')
    assert "onclick=" not in s


def test_escapa_html():
    s = sanear_contexto("<b>negrita</b>")
    assert "&lt;b&gt;" in s


def test_trunca():
    s = sanear_contexto("x" * 200, max_len=50)
    assert len(s) <= 51  # +1 por la elipsis


def test_no_string_devuelve_vacio():
    assert sanear_contexto(None) == ""  # type: ignore[arg-type]
    assert sanear_contexto(123) == ""  # type: ignore[arg-type]


def test_strip_control_chars():
    s = sanear_contexto("hola\x00\x01mundo")
    assert "\x00" not in s and "\x01" not in s
