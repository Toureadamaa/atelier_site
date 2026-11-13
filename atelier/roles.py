"""Роли (действующие лица из главы 2) реализованы группами Django."""
from functools import wraps

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied

KLIENT = "Клиент"
AGENT = "Агент приёма"
UPRAVLYAYUSHII = "Управляющий"
MASTER = "Мастер"
VSE_ROLI = [KLIENT, AGENT, UPRAVLYAYUSHII, MASTER]


def roli(user):
    if not user.is_authenticated:
        return set()
    if user.is_superuser:
        return {AGENT, UPRAVLYAYUSHII}
    return set(user.groups.values_list("name", flat=True))


def est_rol(user, *nuzhnye):
    return bool(roli(user) & set(nuzhnye))


def rol_required(*nuzhnye):
    """Декоратор: доступ к странице только для указанных ролей."""
    def decorator(view):
        @wraps(view)
        @login_required
        def wrapper(request, *args, **kwargs):
            if not est_rol(request.user, *nuzhnye):
                raise PermissionDenied
            return view(request, *args, **kwargs)
        return wrapper
    return decorator
