"""
views.py — Auth + onboarding views for HeartSync.

RegisterView      → create a new account
CreateHouseView   → create a House and get an invite code; optionally email it
JoinHouseView     → join a House with an 8-char invite code
HousePreviewView  → JSON endpoint: returns house name for a given code (live preview)
SendInviteEmailView → POST: email the house invite code to any address
"""

import json
import random
import string

from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.mail import send_mail
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import FormView, TemplateView, RedirectView

from .access import HouseMemberRequiredMixin
from .forms import CreateHouseForm, JoinHouseForm, RegisterForm
from .models import House, Profile


# ---------------------------------------------------------------------------
# Landing page
# ---------------------------------------------------------------------------

class LandingView(TemplateView):
    """Public landing page. Logged-in users are sent straight to the dashboard."""
    template_name = "index.html"

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect("core:dashboard")
        return super().dispatch(request, *args, **kwargs)


INVITE_CODE_CHARS  = string.ascii_uppercase + string.digits
INVITE_CODE_LENGTH = 8


def _generate_unique_invite_code():
    while True:
        code = "".join(random.choices(INVITE_CODE_CHARS, k=INVITE_CODE_LENGTH))
        if not House.objects.filter(invite_code=code).exists():
            return code


def _user_already_has_house(user):
    try:
        return user.profile.house is not None
    except Profile.DoesNotExist:
        return False


# ---------------------------------------------------------------------------
# Welcome — choose create or join (shown after registration, or when logged
# in but not yet in a house)
# ---------------------------------------------------------------------------

class WelcomeView(LoginRequiredMixin, TemplateView):
    template_name = "core/onboarding/welcome.html"

    def dispatch(self, request, *args, **kwargs):
        # Already in a house → skip straight to the app
        if request.user.is_authenticated and _user_already_has_house(request.user):
            return redirect("core:dashboard")
        return super().dispatch(request, *args, **kwargs)


# ---------------------------------------------------------------------------
# Register
# ---------------------------------------------------------------------------

class RegisterView(FormView):
    """Create a new Django User account, then forward to onboarding."""
    template_name = "registration/signup.html"
    form_class    = RegisterForm
    success_url   = reverse_lazy("core:welcome")

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect("core:dashboard")
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        user = form.save()
        login(self.request, user)
        return super().form_valid(form)


# ---------------------------------------------------------------------------
# Create House
# ---------------------------------------------------------------------------

class CreateHouseView(LoginRequiredMixin, FormView):
    template_name = "core/onboarding/create_house.html"
    form_class    = CreateHouseForm
    success_url   = reverse_lazy("core:dashboard")

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and _user_already_has_house(request.user):
            return redirect(self.success_url)
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        data = form.cleaned_data

        with transaction.atomic():
            house = House.objects.create(
                name=data["house_name"],
                invite_code=_generate_unique_invite_code(),
                member_limit=data["member_limit"],
            )
            profile, _ = Profile.objects.get_or_create(user=self.request.user)
            profile.house        = house
            profile.display_name = data["display_name"]
            profile.save(update_fields=["house", "display_name"])

        self.request.session["new_invite_code"] = house.invite_code

        # Optional: send invite email right from the creation form
        invite_email = data.get("invite_email", "").strip()
        if invite_email:
            _send_invite_email(
                to_email=invite_email,
                house=house,
                sender_name=profile.display_name or self.request.user.username,
            )
            messages.success(
                self.request,
                f"Invite email sent to {invite_email}!"
            )

        return super().form_valid(form)


# ---------------------------------------------------------------------------
# Join House
# ---------------------------------------------------------------------------

class JoinHouseView(LoginRequiredMixin, FormView):
    template_name = "core/onboarding/join_house.html"
    form_class    = JoinHouseForm
    success_url   = reverse_lazy("core:dashboard")

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and _user_already_has_house(request.user):
            return redirect(self.success_url)
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        house = form.house

        with transaction.atomic():
            house.refresh_from_db()
            if house.is_full():
                form.add_error(
                    "invite_code",
                    "This home just filled up — ask for a new invite.",
                )
                return self.form_invalid(form)

            profile, _ = Profile.objects.get_or_create(user=self.request.user)
            profile.house        = house
            profile.display_name = form.cleaned_data["display_name"]
            profile.save(update_fields=["house", "display_name"])

        messages.success(
            self.request,
            f"Welcome to {house.name}! 🏠"
        )
        return super().form_valid(form)


# ---------------------------------------------------------------------------
# House preview JSON endpoint (used by join page live preview)
# ---------------------------------------------------------------------------

class HousePreviewView(View):
    """
    GET /onboarding/preview/?code=XXXXXXXX
    Returns {"name": "The Robinsons", "spots_left": 1} or {"error": "..."}
    Only callable by authenticated users; reveals nothing to anonymous callers.
    """

    def get(self, request):
        if not request.user.is_authenticated:
            return JsonResponse({"error": "auth"}, status=401)

        code = request.GET.get("code", "").strip().upper()
        if len(code) != 8:
            return JsonResponse({"error": "too_short"})

        try:
            house = House.objects.get(invite_code=code)
        except House.DoesNotExist:
            return JsonResponse({"error": "not_found"})

        spots_left = max(house.member_limit - house.profiles.count(), 0)
        return JsonResponse({
            "name":       house.name,
            "spots_left": spots_left,
            "is_full":    spots_left == 0,
        })


# ---------------------------------------------------------------------------
# Send invite email from dashboard
# ---------------------------------------------------------------------------

class SendInviteEmailView(HouseMemberRequiredMixin, View):
    """POST /invites/send/ — emails the invite code to the given address."""

    http_method_names = ["post"]

    def post(self, request):
        email = request.POST.get("email", "").strip()
        if not email:
            messages.error(request, "Please enter an email address.")
            return redirect("core:dashboard")

        _send_invite_email(
            to_email=email,
            house=self.house,
            sender_name=request.user.profile.display_name or request.user.username,
        )
        messages.success(request, f"Invite sent to {email} 💌")
        return redirect("core:dashboard")


# ---------------------------------------------------------------------------
# Email helper
# ---------------------------------------------------------------------------

def _send_invite_email(to_email: str, house, sender_name: str):
    join_url = "http://127.0.0.1:8000/onboarding/join/"
    subject  = f"{sender_name} invited you to join {house.name} on HeartSync 💗"
    body = (
        f"Hi there!\n\n"
        f"{sender_name} has invited you to join their home '{house.name}' on HeartSync.\n\n"
        f"Your invite code is:\n\n"
        f"    {house.invite_code}\n\n"
        f"Go to {join_url} and enter the code above to join.\n\n"
        f"— The HeartSync Team 💗"
    )
    send_mail(
        subject=subject,
        message=body,
        from_email=None,   # uses DEFAULT_FROM_EMAIL from settings
        recipient_list=[to_email],
        fail_silently=False,
    )
