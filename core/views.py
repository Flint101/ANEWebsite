from django.core import serializers
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect

from core.forms import Eventform
from core.models import (
    Roster,
    RaidEvent,
    populate_roster_db,
    get_guild_roster,
    Boss,
    LateUser,
    MyUser,
)

from core.utils import (
    get_playable_classes_as_css_classes,
    generate_calendar,
    get_user_display_name, execute_ajax_request, create_initial_roster_json, selected_roster_from_db_to_json,
    user_attendance_status, get_current_user_id,
)


def home_view(request):
    context = {
        'social_user': get_user_display_name(request),
    }
    return render(request, 'home.html', context)


@login_required(login_url='/accounts/battlenet/login/?process=login')
def events_view(request):
    events = RaidEvent.objects.all()

    if events.exists():
        for event in events:
            event.status = user_attendance_status(event, request)

    if request.method == "POST":
        minutes_late = request.POST.get('minutes_late')
        event_date = request.POST.get('date')
        print(minutes_late)
        print(event_date)

        # if LateUser.objects.filter(raid_event=RaidEvent.objects.get(date=event_date)).exists():
        #     print("DATE EXISTS")
        #     obj = LateUser.objects.get(raid_event=RaidEvent.objects.get(date=event_date))
        #     obj.minutes_late = minutes_late
        #     obj.save()
        #
        #
        # else:
        #     LateUser.objects.create(raid_event=RaidEvent.objects.get(date=event_date),
        #                             minutes_late=minutes_late,
        #                             user=MyUser.objects.get(user=request.user))

    context = {
        'event_list': events,
        'social_user': get_user_display_name(request),
    }
    return render(request, 'events.html', context)


def add_event_view(request):
    if request.user.is_superuser:
        return redirect('home')
    submitted = False
    if request.method == "POST":
        form = Eventform(request.POST)
        if form.is_valid():
            form.save()
            api_roster = get_guild_roster(request)
            populate_roster_db(api_roster)
            date = request.POST['date']
            RaidEvent.objects.get(date=date).populate_roster()
            return redirect('events')
    else:
        form = Eventform
        if 'submitted' in request.GET:
            submitted = True

    context = {
        'form': form,
        'submitted': submitted,
    }
    return render(request, 'add_event.html', context)


def events_details_view(request, event_date):
    roster_dict = create_initial_roster_json(event_date)

    execute_ajax_request(event_date, request)

    bosses = serializers.serialize("json", Boss.objects.all())

    roster_per_boss_dict = selected_roster_from_db_to_json(event_date)

    # late_users = RaidEvent.objects.get(date=event_date).late_users.all()

    context = {
        'roster_dict': roster_dict,
        'bosses': bosses,
        'social_user': get_user_display_name(request),
        'css_classes': get_playable_classes_as_css_classes(),
        'selected_roster': roster_per_boss_dict,
        # 'late_users': late_users,
    }
    return render(request, 'events_details.html', context)


def roster_view(request):
    context = {
        'roster': Roster.objects.all(),
        'playable_classes': get_playable_classes_as_css_classes(),
        'social_user': get_user_display_name(request),
    }
    return render(request, 'roster.html', context)


@login_required(login_url='/accounts/battlenet/login/?process=login')
def calendar_view(request):
    events = RaidEvent.objects.all()
    events_dict = {}
    for event in events:
        try:
            event_name = event.name
        except AttributeError:
            event_name = "Raid"

        status = user_attendance_status(event, request)

        events_dict.update({event.id: {
            'event_name': event_name,
            'event_date': event.date,
            'event_id': event.id,
            'event_status': status,

        }})

    cal = generate_calendar(events_dict)

    context = {
        'cal': cal,
        'social_user': get_user_display_name(request),
    }
    return render(request, 'calendar.html', context)
