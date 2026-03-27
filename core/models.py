import datetime

from django.db import models
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.utils import timezone

from .managers import QuestManager, RewardManager


class House(models.Model):
    """
    A private silo for a couple or small family.
    All data is scoped to a House; no cross-house visibility exists.
    """

    COUPLE = 2
    FAMILY = 5
    MEMBER_LIMIT_CHOICES = [
        (COUPLE, "Couple (max 2)"),
        (FAMILY, "Family (max 5)"),
    ]

    name = models.CharField(max_length=100)
    invite_code = models.CharField(
        max_length=8,
        unique=True,
        editable=False,
        help_text="Share this code to invite members. Never searchable.",
    )
    member_limit = models.PositiveSmallIntegerField(
        choices=MEMBER_LIMIT_CHOICES,
        default=COUPLE,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def is_full(self):
        return self.profiles.count() >= self.member_limit

    def __str__(self):
        return f"{self.name} ({self.invite_code})"


class Profile(models.Model):
    """
    Extends the built-in User to link them to exactly one House.
    A user can only belong to one House; joining requires a valid invite_code.
    """

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")
    house = models.ForeignKey(
        House,
        on_delete=models.CASCADE,
        related_name="profiles",
        null=True,
        blank=True,
    )
    display_name = models.CharField(max_length=60, blank=True)
    avatar = models.ImageField(upload_to="avatars/", null=True, blank=True)
    points_balance = models.PositiveIntegerField(default=0)
    total_points_earned = models.PositiveIntegerField(default=0)
    joined_at = models.DateTimeField(auto_now_add=True)

    def award_points(self, amount: int):
        self.points_balance += amount
        self.total_points_earned += amount
        self.save(update_fields=["points_balance", "total_points_earned"])

    def spend_points(self, amount: int):
        if self.points_balance < amount:
            raise ValidationError("Not enough points.")
        self.points_balance -= amount
        self.save(update_fields=["points_balance"])

    def __str__(self):
        return self.display_name or self.user.username


class Quest(models.Model):
    """
    A chore / task linked to a House.
    Completing a Quest awards the claimer points.
    """

    DIFFICULTY_CHOICES = [
        (10, "Easy"),
        (25, "Medium"),
        (50, "Hard"),
        (100, "Epic"),
    ]

    objects = QuestManager()

    house = models.ForeignKey(House, on_delete=models.CASCADE, related_name="quests")
    title = models.CharField(max_length=150)
    description = models.TextField(blank=True)
    points = models.PositiveSmallIntegerField(
        choices=DIFFICULTY_CHOICES,
        default=10,
    )
    assigned_to = models.ForeignKey(
        Profile,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assigned_quests",
    )
    completed_by = models.ForeignKey(
        Profile,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="completed_quests",
    )
    is_completed = models.BooleanField(default=False)
    is_recurring = models.BooleanField(
        default=False,
        help_text="If True, Quest resets after completion.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    def complete(self, profile: Profile):
        """Mark quest done and award points to the completing profile."""
        from django.utils import timezone

        if self.house != profile.house:
            raise ValidationError("Profile does not belong to this House.")
        self.is_completed = True
        self.completed_by = profile
        self.completed_at = timezone.now()
        self.save(update_fields=["is_completed", "completed_by", "completed_at"])
        profile.award_points(self.points)

    def __str__(self):
        status = "✓" if self.is_completed else "○"
        return f"[{status}] {self.title} ({self.points} pts)"


class Reward(models.Model):
    """
    Something points can be redeemed for — e.g. 'Date Night', 'Massage'.
    Scoped to a House so couples can define their own rewards.
    """

    objects = RewardManager()

    house = models.ForeignKey(House, on_delete=models.CASCADE, related_name="rewards")
    title = models.CharField(max_length=150)
    description = models.TextField(blank=True)
    cost = models.PositiveIntegerField(help_text="Points required to redeem.")
    icon = models.CharField(
        max_length=10,
        blank=True,
        help_text="Optional emoji icon, e.g. 💆 or 🍕",
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def redeem(self, profile: Profile):
        """Spend points from a profile's balance to claim this reward."""
        if self.house != profile.house:
            raise ValidationError("Profile does not belong to this House.")
        if not self.is_active:
            raise ValidationError("This reward is no longer available.")
        profile.spend_points(self.cost)
        # Set fulfillment deadline based on reward cost
        if self.cost <= 50:
            weeks = 2
        elif self.cost <= 100:
            weeks = 3
        else:
            weeks = 4
        deadline = timezone.localdate() + datetime.timedelta(weeks=weeks)
        return Redemption.objects.create(reward=self, redeemed_by=profile, deadline=deadline)

    def __str__(self):
        return f"{self.icon} {self.title} — {self.cost} pts"


class Gratitude(models.Model):
    """
    A sticker or short note sent from one housemate to another.
    Stored per-house; never visible outside the House.
    """
    sender    = models.ForeignKey(Profile, on_delete=models.CASCADE, related_name="gratitude_sent")
    recipient = models.ForeignKey(Profile, on_delete=models.CASCADE, related_name="gratitude_received")
    sticker   = models.CharField(max_length=10, blank=True)
    message   = models.TextField(max_length=200, blank=True)
    sent_at   = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.sender} → {self.recipient}: {self.sticker} {self.message[:30]}"


class Redemption(models.Model):
    """
    Audit log of every time a Reward is claimed.
    """

    reward = models.ForeignKey(
        Reward, on_delete=models.CASCADE, related_name="redemptions"
    )
    redeemed_by = models.ForeignKey(
        Profile, on_delete=models.CASCADE, related_name="redemptions"
    )
    redeemed_at = models.DateTimeField(auto_now_add=True)
    is_fulfilled = models.BooleanField(
        default=False,
        help_text="The other partner marks this True when the reward is delivered.",
    )
    deadline = models.DateField(
        null=True,
        blank=True,
        help_text="Date by which the partner should fulfill this reward.",
    )

    @property
    def days_remaining(self):
        if not self.deadline:
            return None
        return (self.deadline - timezone.localdate()).days

    @property
    def is_overdue(self):
        days = self.days_remaining
        return days is not None and days < 0

    def __str__(self):
        return f"{self.redeemed_by} redeemed '{self.reward.title}'"


class ImportantDate(models.Model):
    """
    A memorable date (anniversary, birthday, special moment) for a House.
    Supports yearly recurrence and reminder alerts when the date is near.
    """

    CATEGORY_CHOICES = [
        ("anniversary", "Anniversary"),
        ("birthday", "Birthday"),
        ("special", "Special Moment"),
        ("other", "Other"),
    ]

    CATEGORY_ICONS = {
        "anniversary": "💍",
        "birthday": "🎂",
        "special": "✨",
        "other": "📅",
    }

    house = models.ForeignKey(
        House, on_delete=models.CASCADE, related_name="important_dates"
    )
    title = models.CharField(max_length=150)
    note = models.TextField(blank=True)
    date = models.DateField()
    category = models.CharField(
        max_length=20, choices=CATEGORY_CHOICES, default="other"
    )
    is_recurring = models.BooleanField(
        default=True,
        help_text="If True, the date repeats every year.",
    )
    reminder_days = models.PositiveIntegerField(
        default=7,
        help_text="Show a reminder this many days before the date.",
    )
    created_by = models.ForeignKey(
        Profile, on_delete=models.SET_NULL, null=True, blank=True, related_name="important_dates"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    @property
    def icon(self):
        return self.CATEGORY_ICONS.get(self.category, "📅")

    @property
    def next_occurrence(self):
        """Return the next date this event falls on (handles yearly recurrence)."""
        today = timezone.localdate()
        if not self.is_recurring:
            return self.date
        target = self.date.replace(year=today.year)
        if target < today:
            target = target.replace(year=today.year + 1)
        return target

    @property
    def days_until(self):
        return (self.next_occurrence - timezone.localdate()).days

    @property
    def is_upcoming(self):
        return 0 <= self.days_until <= self.reminder_days

    def __str__(self):
        return f"{self.title} ({self.date})"
