"""
dashboard_views.py — Main app views for HeartSync.

All views here require the user to be authenticated AND belong to a House.
This is enforced by HouseMemberRequiredMixin from access.py.

Views:
    DashboardView    — summary: housemates, points, recent activity
    QuestListView    — browse + complete open quests
    QuestCreateView  — add a new quest to the house
    RewardListView   — browse + redeem rewards
    RewardCreateView — add a new reward to the house
    CompleteQuestView  — POST-only; marks a quest done and awards points
    RedeemRewardView   — POST-only; spends points and logs redemption
    ImportantDateListView   — list all important dates for the house
    ImportantDateCreateView — add a new important date
    ImportantDateDeleteView — delete an important date (POST-only)
"""

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.views.generic import CreateView, ListView, TemplateView, View

from .access import HouseMemberRequiredMixin, get_house_object_or_404
from .forms import ImportantDateForm, QuestForm, RewardForm
from .models import ImportantDate, Quest, Redemption, Reward


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------

class DashboardView(HouseMemberRequiredMixin, TemplateView):
    """
    Landing page after login.
    Shows: housemate list with balances, open quest count, recent redemptions,
    and the one-time invite code banner if a house was just created.
    """
    template_name = "core/dashboard.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        user = self.request.user
        profile = user.profile

        ctx["house"] = self.house
        ctx["profile"] = profile
        ctx["housemates"] = (
            self.house.profiles
            .select_related("user")
            .order_by("-total_points_earned")
        )
        total_quests    = Quest.objects.for_user(user).count()
        completed_quests = Quest.objects.for_user(user).completed().count()
        ctx["open_quest_count"]      = total_quests - completed_quests
        ctx["total_quest_count"]     = total_quests
        ctx["completed_quest_count"] = completed_quests
        # Integer 0-100 used by the power bar width style
        ctx["power_pct"] = int((completed_quests / total_quests * 100) if total_quests else 0)

        ctx["recent_redemptions"] = (
            Redemption.objects
            .filter(reward__house=self.house)
            .select_related("redeemed_by", "reward")
            .order_by("-redeemed_at")[:5]
        )

        ctx["new_invite_code"] = self.request.session.pop("new_invite_code", None)
        ctx["stickers"] = ["🌸", "💪", "🍕", "☕", "🐾", "💖", "🌟", "🎉", "🦋", "🍓"]

        # Deadline alerts for the current user's own redemptions
        ctx["pending_redemptions"] = (
            Redemption.objects
            .filter(redeemed_by=profile, is_fulfilled=False, deadline__isnull=False)
            .select_related("redeemed_by", "reward")
            .order_by("deadline")
        )

        # Redemptions made by OTHER housemates that are unfulfilled — alert current user to fulfill them
        ctx["partner_redemptions"] = (
            Redemption.objects
            .filter(reward__house=self.house, is_fulfilled=False)
            .exclude(redeemed_by=profile)
            .select_related("redeemed_by", "reward")
            .order_by("-redeemed_at")
        )

        # Gratitude received by the current user (most recent 5)
        from .models import Gratitude
        ctx["received_gratitude"] = (
            Gratitude.objects
            .filter(recipient=profile)
            .select_related("sender")
            .order_by("-sent_at")[:5]
        )

        # Important dates — private to whoever created them
        my_dates = ImportantDate.objects.filter(created_by=profile).order_by("date")
        ctx["upcoming_dates"] = [d for d in my_dates if d.is_upcoming]
        ctx["all_important_dates"] = my_dates

        return ctx


# ---------------------------------------------------------------------------
# Quest views
# ---------------------------------------------------------------------------

class QuestListView(HouseMemberRequiredMixin, ListView):
    template_name = "core/quests/list.html"
    context_object_name = "quests"
    paginate_by = 20

    def get_queryset(self):
        user = self.request.user
        qs = Quest.objects.for_user(user).order_by("is_completed", "-created_at")

        # Optional filter via ?filter=mine|completed
        f = self.request.GET.get("filter")
        if f == "mine":
            qs = qs.assigned_to_profile(user.profile)
        elif f == "completed":
            qs = qs.completed()
        else:
            qs = qs.incomplete()

        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["profile"] = self.request.user.profile
        ctx["active_filter"] = self.request.GET.get("filter", "open")
        ctx["filters"] = [
            ("Open", "open"),
            ("Mine", "mine"),
            ("Completed", "completed"),
        ]
        return ctx


class QuestCreateView(HouseMemberRequiredMixin, CreateView):
    template_name = "core/quests/create.html"
    form_class = QuestForm
    success_url = reverse_lazy("core:quest-list")

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        # Pass the house so the form can populate the 'assigned_to' dropdown
        # with only members of this house.
        kwargs["house"] = self.house
        return kwargs

    def form_valid(self, form):
        # Bind the quest to the current house before saving.
        form.instance.house = self.house
        messages.success(self.request, f"Quest '{form.instance.title}' added!")
        return super().form_valid(form)


class CompleteQuestView(HouseMemberRequiredMixin, View):
    """POST-only. Marks a quest complete and awards points to the user."""

    http_method_names = ["post"]

    def post(self, request, pk):
        quest = get_house_object_or_404(Quest, request.user, pk=pk)
        profile = request.user.profile

        if quest.is_completed:
            messages.warning(request, "That quest is already completed.")
            return redirect("core:quest-list")

        try:
            quest.complete(profile)
            messages.success(
                request,
                f"Quest complete! You earned {quest.points} point"
                f"{'s' if quest.points != 1 else ''}."
            )
        except ValidationError as e:
            messages.error(request, str(e))

        return redirect("core:quest-list")


# ---------------------------------------------------------------------------
# Reward views
# ---------------------------------------------------------------------------

class RewardListView(HouseMemberRequiredMixin, ListView):
    template_name = "core/rewards/list.html"
    context_object_name = "rewards"

    def get_queryset(self):
        return Reward.objects.for_user(self.request.user).active().order_by("cost")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["profile"] = self.request.user.profile
        # Tag each reward so the template can grey out unaffordable ones.
        profile = self.request.user.profile
        ctx["affordable_ids"] = set(
            Reward.objects.for_user(self.request.user)
            .affordable_for(profile)
            .values_list("id", flat=True)
        )
        ctx["recent_redemptions"] = (
            Redemption.objects
            .filter(reward__house=self.house)
            .select_related("redeemed_by", "reward")
            .order_by("-redeemed_at")[:10]
        )
        return ctx


class RewardCreateView(HouseMemberRequiredMixin, CreateView):
    template_name = "core/rewards/create.html"
    form_class = RewardForm
    success_url = reverse_lazy("core:reward-list")

    def form_valid(self, form):
        form.instance.house = self.house
        messages.success(self.request, f"Reward '{form.instance.title}' added!")
        return super().form_valid(form)


class RedeemRewardView(HouseMemberRequiredMixin, View):
    """POST-only. Spends points and creates a Redemption record."""

    http_method_names = ["post"]

    def post(self, request, pk):
        reward = get_house_object_or_404(Reward, request.user, pk=pk)
        profile = request.user.profile

        try:
            reward.redeem(profile)
            messages.success(
                request,
                f"You redeemed '{reward.title}'! "
                f"Remaining balance: {profile.points_balance} pts."
            )
        except ValidationError as e:
            messages.error(request, str(e))

        return redirect("core:reward-list")


class FulfillRedemptionView(HouseMemberRequiredMixin, View):
    """POST-only. Marks a Redemption as fulfilled by the other partner."""

    http_method_names = ["post"]

    def post(self, request, pk):
        from django.shortcuts import get_object_or_404
        from .models import Redemption as RedemptionModel
        # Redemption has no direct house FK, so scope via reward__house.
        redemption = get_object_or_404(
            RedemptionModel, pk=pk, reward__house=self.house
        )
        redemption.is_fulfilled = True
        redemption.save(update_fields=["is_fulfilled"])
        messages.success(request, f"'{redemption.reward.title}' marked as done!")
        return redirect("core:reward-list")


class SendGratitudeView(HouseMemberRequiredMixin, View):
    """POST-only. Saves a sticker/note Gratitude object."""

    http_method_names = ["post"]

    def post(self, request):
        from .models import Gratitude, Profile as ProfileModel
        sticker    = request.POST.get("sticker", "").strip()
        message    = request.POST.get("message", "").strip()
        recipient_id = request.POST.get("recipient_id")

        if not sticker and not message:
            messages.error(request, "Pick a sticker or write a note first.")
            return redirect("core:dashboard")

        try:
            recipient = ProfileModel.objects.get(id=recipient_id, house=self.house)
        except ProfileModel.DoesNotExist:
            messages.error(request, "Recipient not found.")
            return redirect("core:dashboard")

        Gratitude.objects.create(
            sender=request.user.profile,
            recipient=recipient,
            sticker=sticker,
            message=message,
        )
        messages.success(request, f"Gratitude sent to {recipient.display_name}! 💗")
        return redirect("core:dashboard")


# ---------------------------------------------------------------------------
# Important Dates views
# ---------------------------------------------------------------------------

class ImportantDateListView(HouseMemberRequiredMixin, ListView):
    template_name = "core/dates/list.html"
    context_object_name = "important_dates"

    def get_queryset(self):
        return ImportantDate.objects.filter(created_by=self.request.user.profile).order_by("date")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["profile"] = self.request.user.profile
        # Annotate each date with days_until so template can use it
        return ctx


class ImportantDateCreateView(HouseMemberRequiredMixin, CreateView):
    template_name = "core/dates/create.html"
    form_class = ImportantDateForm
    success_url = reverse_lazy("core:date-list")

    def form_valid(self, form):
        form.instance.house = self.house
        form.instance.created_by = self.request.user.profile
        messages.success(self.request, f"'{form.instance.title}' saved! 📅")
        return super().form_valid(form)


class ImportantDateDeleteView(HouseMemberRequiredMixin, View):
    """POST-only. Deletes an important date belonging to this house."""

    http_method_names = ["post"]

    def post(self, request, pk):
        date_obj = get_object_or_404(ImportantDate, pk=pk, created_by=request.user.profile)
        title = date_obj.title
        date_obj.delete()
        messages.success(request, f"'{title}' removed.")
        return redirect("core:date-list")
