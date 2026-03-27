from django.urls import path

from . import views
from . import dashboard_views as dv

app_name = "core"

urlpatterns = [
    # ------------------------------------------------------------------
    # Auth
    # ------------------------------------------------------------------
    path("register/",               views.RegisterView.as_view(),          name="register"),
    path("welcome/",                views.WelcomeView.as_view(),           name="welcome"),

    # ------------------------------------------------------------------
    # Onboarding
    # ------------------------------------------------------------------
    path("onboarding/create/",      views.CreateHouseView.as_view(),       name="house-create"),
    path("onboarding/join/",        views.JoinHouseView.as_view(),         name="house-join"),
    path("onboarding/preview/",     views.HousePreviewView.as_view(),      name="house-preview"),

    # ------------------------------------------------------------------
    # Main app
    # ------------------------------------------------------------------
    path("",                        dv.DashboardView.as_view(),            name="dashboard"),

    path("quests/",                 dv.QuestListView.as_view(),            name="quest-list"),
    path("quests/new/",             dv.QuestCreateView.as_view(),          name="quest-create"),
    path("quests/<int:pk>/complete/", dv.CompleteQuestView.as_view(),      name="quest-complete"),

    path("rewards/",                dv.RewardListView.as_view(),           name="reward-list"),
    path("rewards/new/",            dv.RewardCreateView.as_view(),         name="reward-create"),
    path("rewards/<int:pk>/redeem/", dv.RedeemRewardView.as_view(),        name="reward-redeem"),

    path("redemptions/<int:pk>/fulfill/", dv.FulfillRedemptionView.as_view(), name="redemption-fulfill"),
    path("gratitude/send/",         dv.SendGratitudeView.as_view(),        name="send-gratitude"),
    path("invites/send/",           views.SendInviteEmailView.as_view(),   name="send-invite"),

    # ------------------------------------------------------------------
    # Important Dates
    # ------------------------------------------------------------------
    path("dates/",                  dv.ImportantDateListView.as_view(),    name="date-list"),
    path("dates/new/",              dv.ImportantDateCreateView.as_view(),  name="date-create"),
    path("dates/<int:pk>/delete/",  dv.ImportantDateDeleteView.as_view(),  name="date-delete"),
]
