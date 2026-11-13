from django import forms
from django.contrib.auth.models import Group, User

from . import roles
from .models import (Klient, Master, Material, Merki, Model, PoziciyaZakaza, Primerka,
                     Zadacha, Zakaz, Zakupka, Zapis, proverka_v_baze)

DATE = forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d")
TIME = forms.TimeInput(attrs={"type": "time"}, format="%H:%M")


class StyleMixin:
    """Добавляет к полям классы собственной дизайн-системы (css/atelier.css)."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            w = field.widget
            if isinstance(w, forms.CheckboxInput):
                continue  # флажок оформляется обёрткой <label class="check">
            if isinstance(w, forms.Select):
                w.attrs.setdefault("class", "select")
            elif isinstance(w, forms.Textarea):
                w.attrs.setdefault("class", "textarea")
            else:
                w.attrs.setdefault("class", "input")


class AccountMixin(forms.Form):
    """Необязательное создание учётной записи (логин/пароль) для клиента или мастера."""
    login = forms.CharField(label="Логин для входа", max_length=150, required=False,
                            help_text="Оставьте пустым, если вход в систему не нужен.")
    parol = forms.CharField(label="Пароль", required=False, widget=forms.PasswordInput)

    def clean(self):
        data = super().clean()
        login, parol = data.get("login"), data.get("parol")
        if login and User.objects.filter(username=login).exists():
            self.add_error("login", "Такой логин уже занят.")
        if login and not parol:
            self.add_error("parol", "Укажите пароль.")
        return data

    def sozdat_uchetku(self, obj, rol):
        login = self.cleaned_data.get("login")
        if login and obj.user_id is None:
            user = User.objects.create_user(login, password=self.cleaned_data["parol"])
            user.groups.add(Group.objects.get_or_create(name=rol)[0])
            obj.user = user
            obj.save(update_fields=["user"])


class KlientForm(AccountMixin, StyleMixin, forms.ModelForm):
    class Meta:
        model = Klient
        fields = ["fio", "telefon", "email"]


class KlientEditForm(StyleMixin, forms.ModelForm):
    class Meta:
        model = Klient
        fields = ["fio", "telefon", "email"]


class MerkiForm(StyleMixin, forms.ModelForm):
    class Meta:
        model = Merki
        fields = ["grud", "taliya", "bedra", "data_snyatiya"]
        widgets = {"data_snyatiya": DATE}


class ZakazForm(StyleMixin, forms.ModelForm):
    class Meta:
        model = Zakaz
        fields = ["klient", "model", "data_oformleniya", "stoimost"]
        widgets = {"data_oformleniya": DATE}
        help_texts = {"stoimost": "Если не указать — будет взята цена модели."}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["stoimost"].required = False


class ZakazStatusForm(StyleMixin, forms.ModelForm):
    class Meta:
        model = Zakaz
        fields = ["status", "data_zaversheniya", "stoimost"]
        widgets = {"data_zaversheniya": DATE}


class ZapisForm(StyleMixin, forms.ModelForm):
    class Meta:
        model = Zapis
        fields = ["klient", "data", "vremya", "tip_zapisi"]
        widgets = {"data": DATE, "vremya": TIME}


class ZapisKlientaForm(StyleMixin, forms.ModelForm):
    """Запись, которую клиент создаёт сам (клиент подставляется автоматически)."""

    class Meta:
        model = Zapis
        fields = ["data", "vremya", "tip_zapisi"]
        widgets = {"data": DATE, "vremya": TIME}


class ModelForm(StyleMixin, forms.ModelForm):
    class Meta:
        model = Model
        fields = ["nazvanie", "kategoriya", "cena", "opisanie"]
        widgets = {"opisanie": forms.Textarea(attrs={"rows": 3})}


class MasterForm(AccountMixin, StyleMixin, forms.ModelForm):
    class Meta:
        model = Master
        fields = ["fio", "dolzhnost", "stazh", "nomer_telefona"]


class MasterEditForm(StyleMixin, forms.ModelForm):
    class Meta:
        model = Master
        fields = ["fio", "dolzhnost", "stazh", "nomer_telefona", "rabotaet"]


class ZadachaForm(StyleMixin, forms.ModelForm):
    class Meta:
        model = Zadacha
        fields = ["master", "opisanie", "slozhnaya"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["master"].queryset = Master.objects.filter(rabotaet=True)


class ZadachaStatusForm(StyleMixin, forms.ModelForm):
    class Meta:
        model = Zadacha
        fields = ["status", "kommentarii"]
        widgets = {"kommentarii": forms.TextInput(attrs={"placeholder": "Комментарий для управляющего"})}


class PrimerkaForm(StyleMixin, forms.ModelForm):
    class Meta:
        model = Primerka
        fields = ["data", "vremya", "master"]
        widgets = {"data": DATE, "vremya": TIME}
        help_texts = {"master": "Если не выбрать — назначится самый опытный мастер, свободный в это время."}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        m = self.fields["master"]
        m.queryset = Master.objects.filter(rabotaet=True, dolzhnost__in=Primerka.DOLZHNOSTI_PRIMERKI).order_by("-stazh", "fio")
        m.empty_label = "Автоматически — самый опытный свободный"
        m.label_from_instance = lambda x: f"{x.fio} — {x.dolzhnost}, стаж {x.stazh}"


class PrimerkaRezultatForm(StyleMixin, forms.ModelForm):
    class Meta:
        model = Primerka
        fields = ["rezultat"]
        widgets = {"rezultat": forms.Textarea(attrs={"rows": 2})}


class PoziciyaZakazaForm(StyleMixin, forms.ModelForm):
    class Meta:
        model = PoziciyaZakaza
        fields = ["material", "kolichestvo"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # в заказ можно добавлять только материалы, которые есть на складе
        self.fields["material"].queryset = Material.objects.filter(ostatok__gt=0)


class MaterialForm(StyleMixin, forms.ModelForm):
    class Meta:
        model = Material
        fields = ["nazvanie", "tip", "edinica_izmereniya"]


class ZakupkaForm(StyleMixin, forms.ModelForm):
    class Meta:
        model = Zakupka
        fields = ["data", "postavshik"]
        widgets = {"data": DATE}


class PoziciiZakupkiForm(StyleMixin, forms.Form):
    """Позиции закупки: несколько строк «материал — количество»."""
    STROK = 5

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for i in range(self.STROK):
            self.fields[f"material_{i}"] = forms.ModelChoiceField(
                Material.objects.all(), required=False, label="Материал",
                widget=forms.Select(attrs={"class": "select"}))
            # ограничение 20 (количество >= 1) проверяет SQL Server, если включена PROVERKA_V_BAZE
            self.fields[f"kolichestvo_{i}"] = forms.DecimalField(
                required=False, min_value=None if proverka_v_baze() else 1,
                max_digits=10, decimal_places=2,
                label="Количество", widget=forms.NumberInput(attrs={"class": "input"}))

    def stroki(self):
        return [(self[f"material_{i}"], self[f"kolichestvo_{i}"]) for i in range(self.STROK)]

    def clean(self):
        data = super().clean()
        pozicii, vidennye = [], set()
        for i in range(self.STROK):
            m, q = data.get(f"material_{i}"), data.get(f"kolichestvo_{i}")
            if m is None and q is None:
                continue
            if m is None or q is None:
                raise forms.ValidationError(f"Строка {i + 1}: укажите и материал, и количество.")
            if m.pk in vidennye:
                raise forms.ValidationError(f"Материал «{m.nazvanie}» указан дважды.")
            vidennye.add(m.pk)
            pozicii.append((m, q))
        if not pozicii:
            raise forms.ValidationError("Добавьте хотя бы одну позицию.")
        data["pozicii"] = pozicii
        return data
