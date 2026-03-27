from django.contrib import admin
from .models import House, Profile, Quest, Reward, Redemption, Gratitude

@admin.register(House)
class HouseAdmin(admin.ModelAdmin):
    list_display  = ["name", "invite_code", "member_limit", "created_at"]
    readonly_fields = ["invite_code"]

@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display  = ["user", "house", "display_name", "points_balance"]
    list_filter   = ["house"]

@admin.register(Quest)
class QuestAdmin(admin.ModelAdmin):
    list_display  = ["title", "house", "points", "is_completed", "assigned_to"]
    list_filter   = ["house", "is_completed"]

@admin.register(Reward)
class RewardAdmin(admin.ModelAdmin):
    list_display  = ["title", "house", "cost", "is_active"]
    list_filter   = ["house"]

@admin.register(Redemption)
class RedemptionAdmin(admin.ModelAdmin):
    list_display  = ["reward", "redeemed_by", "redeemed_at", "is_fulfilled"]

@admin.register(Gratitude)
class GratitudeAdmin(admin.ModelAdmin):
    list_display  = ["sender", "recipient", "sticker", "sent_at"]
