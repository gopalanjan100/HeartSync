"""
forms.py — All forms for HeartSync.

Onboarding:
    CreateHouseForm  → user picks a House name and their own display name.
    JoinHouseForm    → user enters an 8-character invite code.

Main app:
    QuestForm        → add a new Quest to the house.
    RewardForm       → add a new Reward to the house.
"""

from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError

from .models import House, ImportantDate, Profile, Quest, Reward


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

class RegisterForm(UserCreationForm):
    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={"placeholder": "you@example.com", "autocomplete": "email"}),
    )

    class Meta:
        model  = User
        fields = ["username", "email", "password1", "password2"]

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data["email"]
        if commit:
            user.save()
        return user


# ---------------------------------------------------------------------------
# Create House
# ---------------------------------------------------------------------------

class CreateHouseForm(forms.Form):
    house_name = forms.CharField(
        max_length=100,
        label="House Name",
        help_text="e.g. 'The Robinsons' or 'Our Little Nest'",
        widget=forms.TextInput(attrs={
            "placeholder": "Give your home a name",
            "autocomplete": "off",
        }),
    )
    member_limit = forms.ChoiceField(
        choices=House.MEMBER_LIMIT_CHOICES,
        label="Who lives here?",
        help_text="Couple (max 2) or Family (max 5). This cannot be changed later.",
        widget=forms.RadioSelect,
    )
    display_name = forms.CharField(
        max_length=60,
        label="Your Display Name",
        help_text="What should your housemates call you?",
        widget=forms.TextInput(attrs={
            "placeholder": "e.g. Alex",
            "autocomplete": "off",
        }),
    )

    invite_email = forms.EmailField(
        required=False,
        label="Invite Someone (optional)",
        help_text="Enter their email and we'll send the invite code for you.",
        widget=forms.EmailInput(attrs={
            "placeholder": "partner@example.com",
            "autocomplete": "off",
        }),
    )

    def clean_member_limit(self):
        """Coerce the string choice value back to int."""
        return int(self.cleaned_data["member_limit"])


# ---------------------------------------------------------------------------
# Join House
# ---------------------------------------------------------------------------

class JoinHouseForm(forms.Form):
    invite_code = forms.CharField(
        max_length=8,
        min_length=8,
        label="Invite Code",
        help_text="Enter the 8-character code shared by your partner or family member.",
        widget=forms.TextInput(attrs={
            "placeholder": "e.g. A3F9K2ZX",
            "autocomplete": "off",
            "style": "text-transform: uppercase; letter-spacing: 0.2em;",
        }),
    )
    display_name = forms.CharField(
        max_length=60,
        label="Your Display Name",
        widget=forms.TextInput(attrs={
            "placeholder": "e.g. Jordan",
            "autocomplete": "off",
        }),
    )

    def clean_invite_code(self):
        code = self.cleaned_data["invite_code"].strip().upper()

        # --- Gate 1: does this House exist? ---
        try:
            house = House.objects.get(invite_code=code)
        except House.DoesNotExist:
            # Deliberately vague: don't confirm or deny a house at any code.
            raise ValidationError(
                "That invite code is not valid. Double-check with the person who invited you."
            )

        # --- Gate 2: is there room? ---
        if house.is_full():
            limit = house.member_limit
            raise ValidationError(
                f"This home has already reached its limit of {limit} member"
                f"{'s' if limit > 1 else ''}. "
                "Ask the house creator to start a new one if needed."
            )

        # Stash the resolved House on the form so the view doesn't re-query.
        self._house = house
        return code

    @property
    def house(self):
        """
        Returns the validated House instance after is_valid() passes.
        Call this in the view instead of re-querying the DB.
        """
        return getattr(self, "_house", None)


# ---------------------------------------------------------------------------
# Quest (create)
# ---------------------------------------------------------------------------

class QuestForm(forms.ModelForm):
    class Meta:
        model = Quest
        fields = ["title", "description", "points", "assigned_to", "is_recurring"]
        widgets = {
            "title": forms.TextInput(attrs={"placeholder": "e.g. Do the dishes"}),
            "description": forms.Textarea(attrs={"rows": 3, "placeholder": "Optional details…"}),
            "points": forms.Select(),
            "assigned_to": forms.Select(),
            "is_recurring": forms.CheckboxInput(),
        }

    def __init__(self, *args, house=None, **kwargs):
        super().__init__(*args, **kwargs)
        # Restrict the 'assigned_to' dropdown to members of this House only.
        # Without this, the dropdown would list Profiles from every House.
        if house is not None:
            self.fields["assigned_to"].queryset = Profile.objects.filter(house=house)
        self.fields["assigned_to"].required = False
        self.fields["assigned_to"].empty_label = "Anyone"


# ---------------------------------------------------------------------------
# Reward (create)
# ---------------------------------------------------------------------------

class RewardForm(forms.ModelForm):
    class Meta:
        model = Reward
        fields = ["title", "description", "cost", "icon"]
        widgets = {
            "title": forms.TextInput(attrs={"placeholder": "e.g. Date Night"}),
            "description": forms.Textarea(attrs={"rows": 3, "placeholder": "Optional details…"}),
            "cost": forms.NumberInput(attrs={"min": 1, "placeholder": "Points required"}),
            "icon": forms.TextInput(attrs={"placeholder": "e.g. 💆", "maxlength": 10}),
        }


# ---------------------------------------------------------------------------
# Important Date (create)
# ---------------------------------------------------------------------------

class ImportantDateForm(forms.ModelForm):
    class Meta:
        model = ImportantDate
        fields = ["title", "date", "category", "note", "is_recurring", "reminder_days"]
        widgets = {
            "title": forms.TextInput(attrs={"placeholder": "e.g. First Date Anniversary"}),
            "date": forms.DateInput(attrs={"type": "date"}),
            "category": forms.Select(),
            "note": forms.Textarea(attrs={"rows": 3, "placeholder": "Optional note or memory…"}),
            "is_recurring": forms.CheckboxInput(),
            "reminder_days": forms.NumberInput(attrs={"min": 1, "max": 30, "placeholder": "7"}),
        }
