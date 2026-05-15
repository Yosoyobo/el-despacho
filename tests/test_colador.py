"""El Colador — saneador de reportes."""

from lib.colador import colar_reporte


def test_paths_sistema_redactados():
    out = colar_reporte("error en /opt/el-despacho/.env y /home/despacho/.ssh/id_ed25519")
    assert "/opt/el-despacho/.env" not in out
    assert "/home/despacho" not in out
    assert "[REDACTED:path]" in out


def test_path_relativo_sobrevive():
    # apps/los_ajustes/views.py:42 es útil para debug.
    out = colar_reporte("File apps/los_ajustes/views.py line 42")
    assert "apps/los_ajustes/views.py" in out


def test_api_keys_redactadas():
    out = colar_reporte("key=sk-ant-test-aaaaaaaaaaaaaaaaaaaaaaaaaaaa")
    assert "sk-ant-test" not in out
    assert "[REDACTED:api_key]" in out

    out2 = colar_reporte("Bearer abcdef0123456789abcdef0123456789abcdef01")
    assert "Bearer abc" not in out2
    assert "[REDACTED" in out2


def test_sql_redactada():
    out = colar_reporte("query: SELECT * FROM cuentas_usuario WHERE rol='admin'")
    assert "SELECT" not in out
    assert "[REDACTED:sql]" in out


def test_ip_redactada():
    out = colar_reporte("conectado a 192.168.1.1 y a 2001:0db8:85a3:0000:0000:8a2e:0370:7334")
    assert "192.168.1.1" not in out
    assert "2001:0db8:85a3" not in out
    assert "[REDACTED:ip]" in out


def test_hash_git_sha1_sobrevive():
    sha = "a" * 40
    out = colar_reporte(f"commit {sha} en main")
    assert sha in out


def test_idempotente():
    txt = "key sk-ant-test-aaaaaaaaaaaaaaaaaaaaaaaaaaaa ip 10.0.0.1"
    a = colar_reporte(txt)
    b = colar_reporte(a)
    assert a == b


def test_no_string():
    assert colar_reporte(None) == ""  # type: ignore[arg-type]
    assert colar_reporte("") == ""
