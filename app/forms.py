"""
forms.py
========
Form basati su Flask-WTF per le pagine "classiche" (non-AJAX). Le
modifiche "al volo" sulla dashboard passano invece dagli endpoint JSON in
app/api/routes.py e non usano questi form.
"""

from flask_wtf import FlaskForm
from wtforms import (
    StringField, PasswordField, SelectField, IntegerField, TextAreaField,
    DateField, BooleanField, SubmitField, FloatField,
)
from wtforms.validators import DataRequired, Length, EqualTo, NumberRange, Optional

from app.models import QuantityRule, UserRole, LuggageType


class DecimalCommaFloatField(FloatField):
    """
    Come FloatField, ma segue la convenzione italiana/internazionale dei
    numeri: il PUNTO è SEMPRE il separatore delle migliaia (viene
    rimosso), la VIRGOLA è SEMPRE il separatore decimale. Es. "1.500,5"
    -> 1500.5; "2,5" -> 2.5; "1.500" -> 1500 (non 1,5!).

    Anche il valore ripresentato nel campo quando si modifica un dato già
    salvato segue la stessa convenzione (vedi _value()): così ridigitare
    senza cambiare un valore esistente funziona sempre correttamente,
    senza ambiguità tra "punto usato come decimale per abitudine" e
    "punto come separatore delle migliaia".
    """

    def process_formdata(self, valuelist):
        if not valuelist or not valuelist[0]:
            self.data = None
            return
        from app.utils import parse_number_it
        try:
            self.data = parse_number_it(valuelist[0])
        except (ValueError, TypeError) as exc:
            self.data = None
            raise ValueError(self.gettext("Non è un numero valido.")) from exc

    def _value(self):
        if self.raw_data:
            return self.raw_data[0]
        if self.data is not None:
            from app.utils import format_number_it
            return format_number_it(self.data, decimals=4)
        return ""


class LoginForm(FlaskForm):
    username = StringField("Utente", validators=[DataRequired(), Length(max=80)])
    password = PasswordField("Password", validators=[DataRequired()])
    submit = SubmitField("Accedi")


class ChangePasswordForm(FlaskForm):
    current_password = PasswordField("Password attuale", validators=[DataRequired()])
    new_password = PasswordField(
        "Nuova password", validators=[DataRequired(), Length(min=4, max=128)]
    )
    confirm_password = PasswordField(
        "Conferma nuova password",
        validators=[DataRequired(), EqualTo("new_password", message="Le password non coincidono.")],
    )
    submit = SubmitField("Aggiorna password")


class CategoryForm(FlaskForm):
    name = StringField("Nome categoria", validators=[DataRequired(), Length(max=120)])
    color = StringField("Colore", validators=[DataRequired(), Length(min=4, max=7)])
    icon = StringField("Icona", validators=[Optional(), Length(max=40)])
    submit = SubmitField("Salva categoria")


class ItemForm(FlaskForm):
    name = StringField("Nome oggetto", validators=[DataRequired(), Length(max=150)])
    category_id = SelectField("Categoria", coerce=int, validators=[DataRequired()])
    quantity_rule = SelectField(
        "Regola quantità", choices=QuantityRule.CHOICES, validators=[DataRequired()]
    )
    fixed_qty = IntegerField(
        "Quantità fissa", validators=[Optional(), NumberRange(min=0, max=999)], default=1
    )
    per_day_extra = IntegerField(
        "Cambi extra oltre ai giorni di viaggio",
        validators=[Optional(), NumberRange(min=0, max=99)],
        default=1,
    )
    default_luggage_type = SelectField(
        "Tipologia di valigia predefinita", validators=[Optional()]
    )
    weight_grams = DecimalCommaFloatField(
        "Peso di una unità (grammi)", validators=[Optional(), NumberRange(min=0, max=100000)]
    )
    notes = TextAreaField("Note", validators=[Optional(), Length(max=2000)])
    submit = SubmitField("Salva oggetto")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.default_luggage_type.choices = [("", "— Nessuna (solo manuale) —")] + LuggageType.CHOICES


class ItemVariantForm(FlaskForm):
    """
    Un "modello" specifico di un oggetto (es. per "Camicie": una camicia
    bianca elegante, una casual azzurra, ognuna col proprio peso). Vedi
    models.py::ItemVariant.
    """
    description = StringField("Modello", validators=[DataRequired(), Length(max=200)])
    weight_grams = DecimalCommaFloatField(
        "Peso (grammi)", validators=[Optional(), NumberRange(min=0, max=100000)]
    )
    owned_qty = IntegerField(
        "Quanti ne possiedo", validators=[Optional(), NumberRange(min=0, max=999)], default=1
    )
    submit = SubmitField("Salva modello")


class TripForm(FlaskForm):
    destination = StringField("Meta del viaggio", validators=[DataRequired(), Length(max=150)])
    start_date = DateField("Data di partenza", validators=[DataRequired()])
    end_date = DateField("Data di ritorno", validators=[DataRequired()])
    notes = TextAreaField("Note", validators=[Optional(), Length(max=2000)])
    cover_search_terms = StringField(
        "Termini di ricerca immagine (facoltativo)", validators=[Optional(), Length(max=200)]
    )
    copy_from_trip_id = SelectField(
        "Copia quantità e note dall'ultimo viaggio", coerce=int, validators=[Optional()]
    )
    submit = SubmitField("Salva viaggio")

    def validate(self, extra_validators=None):
        ok = super().validate(extra_validators=extra_validators)
        if ok and self.end_date.data and self.start_date.data:
            if self.end_date.data < self.start_date.data:
                self.end_date.errors.append("La data di ritorno non può precedere la partenza.")
                ok = False
        return ok


class LuggageForm(FlaskForm):
    brand = StringField("Marca", validators=[Optional(), Length(max=120)])
    name = StringField("Nome / modello", validators=[DataRequired(), Length(max=150)])
    tipologia = SelectField("Tipologia", choices=LuggageType.CHOICES, validators=[DataRequired()])
    weight_kg = DecimalCommaFloatField(
        "Peso a vuoto (kg)", validators=[Optional(), NumberRange(min=0, max=200)]
    )
    capacity_liters = DecimalCommaFloatField(
        "Capacità interna (litri)", validators=[Optional(), NumberRange(min=0, max=1000)]
    )
    is_default_for_new_trip = BooleanField("Attiva automaticamente su ogni nuovo viaggio")
    notes = TextAreaField("Note", validators=[Optional(), Length(max=2000)])
    submit = SubmitField("Salva valigia")


class NewUserForm(FlaskForm):
    username = StringField("Nickname (per l'accesso)", validators=[DataRequired(), Length(max=80)])
    full_name = StringField("Nome e cognome", validators=[Optional(), Length(max=150)])
    password = PasswordField(
        "Password iniziale", validators=[DataRequired(), Length(min=4, max=128)]
    )
    role = SelectField(
        "Ruolo",
        choices=[(UserRole.MEMBER, "Membro"), (UserRole.ADMIN, "Amministratore")],
        default=UserRole.MEMBER,
    )
    submit = SubmitField("Crea utente")


class EditUserForm(FlaskForm):
    username = StringField("Nickname (per l'accesso)", validators=[DataRequired(), Length(max=80)])
    full_name = StringField("Nome e cognome", validators=[Optional(), Length(max=150)])
    submit = SubmitField("Salva")


class ShareTripForm(FlaskForm):
    user_id = SelectField("Condividi con", coerce=int, validators=[DataRequired()])
    submit = SubmitField("Condividi")


class CatalogPrefsForm(FlaskForm):
    column_style = SelectField(
        "Colonne del catalogo",
        choices=[("auto", "Automatico (icone su mobile, testo su desktop)"), ("icons", "Sempre icone"), ("text", "Sempre testo")],
    )
    icon_fixed = StringField("Icona per \"Fissa\"", validators=[Optional(), Length(max=60)])
    icon_per_day = StringField("Icona per \"Per giorno\"", validators=[Optional(), Length(max=60)])
    icon_manual = StringField("Icona per \"Manuale\"", validators=[Optional(), Length(max=60)])
    icon_cabina = StringField("Icona per \"Cabina\"", validators=[Optional(), Length(max=60)])
    icon_stiva = StringField("Icona per \"Stiva\"", validators=[Optional(), Length(max=60)])
    icon_zaino = StringField("Icona per \"Zaino\"", validators=[Optional(), Length(max=60)])
    submit = SubmitField("Salva preferenze")
