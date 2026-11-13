from pathlib import Path

from .roles import roli

_STATIC = Path(__file__).resolve().parent / "static" / "atelier"


def rol(request):
    r = roli(request.user)
    return {"roli": r, "is_klient": "Клиент" in r, "is_agent": "Агент приёма" in r,
            "is_upr": "Управляющий" in r, "is_master": "Мастер" in r,
            "v": versiya_static()}


def versiya_static():
    """Номер версии CSS/JS для ссылок (…/atelier.css?v=…): меняется при каждом изменении файлов,
    поэтому браузер не показывает устаревший стиль из кэша."""
    try:
        return max(int(p.stat().st_mtime) for p in (_STATIC / "css" / "atelier.css", _STATIC / "js" / "atelier.js"))
    except OSError:
        return 0
