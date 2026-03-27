"""
access.py — House-level access control for HeartSync.
"""

from functools import wraps

from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import ObjectDoesNotExist
from django.http import Http404
from django.shortcuts import redirect
from django.urls import reverse


JOIN_OR_CREATE_HOUSE_URL = "core:welcome"


def _get_house_or_redirect(user):
    """
    Returns (house, None) on success.
    Returns (None, redirect_response) when the user has no valid House.
    """
    try:
        house = user.profile.house
    except ObjectDoesNotExist:
        return None, redirect(reverse(JOIN_OR_CREATE_HOUSE_URL))

    if house is None:
        return None, redirect(reverse(JOIN_OR_CREATE_HOUSE_URL))

    return house, None


# ---------------------------------------------------------------------------
# Mixin — use with class-based views
# ---------------------------------------------------------------------------

class HouseMemberRequiredMixin(LoginRequiredMixin):
    """
    CBV mixin that gates on authentication first, then House membership.
    Sets self.house before any get()/post() handler runs.
    """

    def dispatch(self, request, *args, **kwargs):
        # Gate 1 — authentication. handle_no_permission() redirects to login.
        if not request.user.is_authenticated:
            return self.handle_no_permission()

        # Gate 2 — House membership.
        house, redirect_response = _get_house_or_redirect(request.user)
        if redirect_response:
            return redirect_response

        # Inject house onto the view so every handler can use self.house.
        self.house = house

        # Skip LoginRequiredMixin in the MRO (already handled above) and
        # go straight to View.dispatch() which routes to get()/post()/etc.
        return super(LoginRequiredMixin, self).dispatch(request, *args, **kwargs)


# ---------------------------------------------------------------------------
# Decorator — use with function-based views
# ---------------------------------------------------------------------------

def house_member_required(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect(f"{reverse('login')}?next={request.path}")

        house, redirect_response = _get_house_or_redirect(request.user)
        if redirect_response:
            return redirect_response

        request.house = house
        return view_func(request, *args, **kwargs)

    return wrapper


# ---------------------------------------------------------------------------
# Row-level get_or_404 helper
# ---------------------------------------------------------------------------

def get_house_object_or_404(model, user, **lookup):
    """
    Fetches model(**lookup) and enforces it belongs to the user's House.
    Raises Http404 for both not-found and wrong-house cases (no info leak).
    """
    try:
        house = user.profile.house
        if house is None:
            raise Http404
    except ObjectDoesNotExist:
        raise Http404

    try:
        return model.objects.get(house=house, **lookup)
    except model.DoesNotExist:
        raise Http404
