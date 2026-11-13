from django import template
from django.utils.safestring import mark_safe

register = template.Library()

# класс «пилюли» статуса (цвет точки + фон); текст статуса всегда выводится рядом
KLASSY = {
    "новый": "s-new", "в работе": "s-work", "примерка": "s-fit", "готов": "s-ready",
    "выдан": "s-done", "отменён": "s-cancel",
    "назначена": "s-new", "выполнена": "s-ready", "проблема": "s-cancel",
}

KATEGORII = {"платье": "plate", "костюм": "kost", "пальто": "palto", "юбка": "yubka",
             "брюки": "bryuki", "рубашка": "rubashka"}

ETAPY = [("новый", "Принят"), ("в работе", "Пошив"), ("примерка", "Примерка"),
         ("готов", "Готов"), ("выдан", "Выдан")]

MESYACY = ["янв", "фев", "мар", "апр", "мая", "июн", "июл", "авг", "сен", "окт", "ноя", "дек"]


@register.filter
def st(status):
    return KLASSY.get(status, "s-new")


# совместимость со старыми шаблонами
status_cls = register.filter("status_cls", st)


@register.filter
def kat(kategoriya):
    return KATEGORII.get(kategoriya, "plate")


@register.filter
def initials(fio):
    chasti = str(fio or "").split()
    return "".join(c[0] for c in chasti[:2]).upper() or "?"


@register.filter
def mes(data):
    return MESYACY[data.month - 1] if data else ""


@register.filter
def rub(value):
    """12500.00 → «12 500»"""
    try:
        return f"{float(value):,.0f}".replace(",", " ")
    except (TypeError, ValueError):
        return value


@register.filter
def plural(n, formy):
    """{{ 5|plural:"год,года,лет" }} → «лет»"""
    odin, dva, pyat = formy.split(",")
    try:
        n = abs(int(n))
    except (TypeError, ValueError):
        return pyat
    if n % 10 == 1 and n % 100 != 11:
        return odin
    if 2 <= n % 10 <= 4 and not 12 <= n % 100 <= 14:
        return dva
    return pyat


@register.filter
def fio_kratko(fio):
    """«Петрова Мария Викторовна» → «Петрова М. В.»"""
    chasti = str(fio or "").split()
    return " ".join(chasti[:1] + [c[0] + "." for c in chasti[1:3]])


@register.inclusion_tag("atelier/_field.html")
def field(f):
    return {"f": f}


@register.inclusion_tag("atelier/_stepper.html")
def stepper(status, mini=False):
    kody = [k for k, _ in ETAPY]
    tek = kody.index(status) if status in kody else -1
    shagi = [{"label": label, "state": "done" if i < tek else ("cur" if i == tek else "")}
             for i, (_, label) in enumerate(ETAPY)]
    return {"shagi": shagi, "mini": mini, "otmenen": status == "отменён"}


@register.inclusion_tag("atelier/_garment.html")
def garment(kategoriya):
    return {"k": KATEGORII.get(kategoriya, "plate")}


@register.simple_tag
def icon(name, cls=""):
    return mark_safe(f'<svg class="ic {cls}" aria-hidden="true"><use href="#i-{name}"/></svg>')
