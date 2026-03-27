"""
managers.py — Custom QuerySet managers for HeartSync.

Every public-facing queryset for Quest and Reward is automatically
filtered to the current user's House, so a developer cannot accidentally
expose cross-house data by forgetting a .filter(house=...) call.

Usage in a view:
    quests = Quest.objects.for_user(request.user).filter(is_completed=False)
    rewards = Reward.objects.for_user(request.user).active()
"""

from django.db import models


# ---------------------------------------------------------------------------
# Shared base
# ---------------------------------------------------------------------------

class HouseScopedQuerySet(models.QuerySet):
    """
    A QuerySet that knows how to scope itself to a single House.
    Subclassed by Quest and Reward querysets.
    """

    def for_house(self, house):
        """Filter to a specific House instance."""
        return self.filter(house=house)

    def for_user(self, user):
        """
        Filter to the House that belongs to *user*.
        Raises AttributeError if the user has no Profile or no House yet
        (handled gracefully by HouseMemberRequired before reaching a view).
        """
        return self.filter(house=user.profile.house)


class HouseScopedManager(models.Manager):
    """
    Base manager that returns a HouseScopedQuerySet.
    Attach this as `objects` on any house-scoped model.
    """

    def get_queryset(self):
        return HouseScopedQuerySet(self.model, using=self._db)

    def for_house(self, house):
        return self.get_queryset().for_house(house)

    def for_user(self, user):
        return self.get_queryset().for_user(user)


# ---------------------------------------------------------------------------
# Quest manager
# ---------------------------------------------------------------------------

class QuestQuerySet(HouseScopedQuerySet):
    """Extended queryset with Quest-specific filters."""

    def incomplete(self):
        return self.filter(is_completed=False)

    def completed(self):
        return self.filter(is_completed=True)

    def assigned_to_profile(self, profile):
        return self.filter(assigned_to=profile)

    def recurring(self):
        return self.filter(is_recurring=True)


class QuestManager(models.Manager):
    def get_queryset(self):
        return QuestQuerySet(self.model, using=self._db)

    # Proxy convenience methods so callers never touch .get_queryset() directly
    def for_house(self, house):
        return self.get_queryset().for_house(house)

    def for_user(self, user):
        return self.get_queryset().for_user(user)

    def incomplete(self):
        return self.get_queryset().incomplete()

    def completed(self):
        return self.get_queryset().completed()


# ---------------------------------------------------------------------------
# Reward manager
# ---------------------------------------------------------------------------

class RewardQuerySet(HouseScopedQuerySet):
    """Extended queryset with Reward-specific filters."""

    def active(self):
        return self.filter(is_active=True)

    def affordable_for(self, profile):
        """Return rewards the profile can currently afford."""
        return self.active().filter(cost__lte=profile.points_balance)


class RewardManager(models.Manager):
    def get_queryset(self):
        return RewardQuerySet(self.model, using=self._db)

    def for_house(self, house):
        return self.get_queryset().for_house(house)

    def for_user(self, user):
        return self.get_queryset().for_user(user)

    def active(self):
        return self.get_queryset().active()

    def affordable_for(self, profile):
        return self.get_queryset().affordable_for(profile)
