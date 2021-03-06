import json
from datetime import datetime, timedelta, timezone
import requests

from allauth.socialaccount.models import SocialAccount, SocialToken
from django.core import serializers
from django.shortcuts import redirect
from django.contrib.auth.models import Group

from core.models import BossWishes, RaidEvent, BossPerEvent, Boss, Roster, LateUser, MyUser, get_user_profile_data, \
    set_account_id_and_class, get_guild_roster, populate_roster_db, populate_user_characters, \
    sync_roster_from_user_characters, AbsentUser


def get_playable_classes_as_css_classes():
    playable_classes = {
        'Warrior': 'warrior',
        'Paladin': 'paladin',
        'Hunter': 'hunter',
        'Rogue': 'rogue',
        'Priest': 'priest',
        'Shaman': 'shaman',
        'Mage': 'mage',
        'Warlock': 'warlock',
        'Monk': 'monk',
        'Druid': 'druid',
        'Demon Hunter': 'demonhunter',
        'Death Knight': 'deathknight',
    }
    return playable_classes


def get_coming_raid_days(amount_of_raids):
    raid_days = [0, 2, 6]  # Monday, Wednesday, Sunday
    current_day = datetime.now()

    raid_dates_in_future = []
    index = 0
    while len(raid_dates_in_future) < amount_of_raids:
        day_in_future = current_day + timedelta(index)
        index = index + 1
        if day_in_future.weekday() in raid_days:
            raid_dates_in_future.append(day_in_future)

    return raid_dates_in_future


def generate_future_events():
    for day in get_coming_raid_days(9):
        day = day.date().strftime('%Y-%m-%d')

        try:
            RaidEvent.objects.get(date=day)
        except RaidEvent.DoesNotExist:
            obj = RaidEvent.objects.create(date=day)
            # obj.populate_roster()


def generate_calendar(events):
    weeks_to_show = 3
    days_to_show = weeks_to_show * 7

    # current_date.weekday() returns a number from 0-6 so create a dict to translate it to a string

    days_of_week = {
        0: "Mon",
        1: "Tues",
        2: "Wed",
        3: "Thurs",
        4: "Fri",
        5: "Satur",
        6: "Sun",
    }

    # Calendar should start on wednesday - Get current weekday and go back x days to get to last wednesday
    # Current date
    current_date = datetime.now()
    day_of_week = current_date.weekday()  # 0 - 6
    # How far to go back to get to last wednesday
    # weekday from current_date.weekday(): how far to go back
    deltadays = {
        0: 5,
        1: 6,
        2: 0,
        3: 1,
        4: 2,
        5: 3,
        6: 4,
    }
    # timedelta() adds/removes X amount of days from current_date
    last_wednesday = current_date - timedelta(deltadays.get(day_of_week))

    # string to send to page - formatted as html
    calendarhtml = ""
    for day in range(days_to_show):
        day_in_future = last_wednesday + timedelta(day)
        # current refers to the day in the future
        current_day_of_month = day_in_future.day
        day_of_week = day_in_future.weekday()
        current_year = day_in_future.year
        current_month = day_in_future.month

        # If day is todays date make it highlighted
        day_status = ""
        if day_in_future == current_date:
            day_status = "active"

        # If day is before todays date disable it
        if day_in_future < current_date:
            day_status = "disabled"

        calendarhtml += "<div class='calendar-grid-item %s calendar-day-%s'>" % (
            day_status, days_of_week.get(day_of_week))
        calendarhtml += "<div class='calendar-grid-date'>%s-%s</div>" % (
            current_day_of_month, current_month)
        calendarhtml += "<div class='calendar-grid-item-content'>"

        for index in events:
            # Index == ID
            if events[index]['event_date'].year == current_year:
                if events[index]['event_date'].month == current_month:
                    if events[index]['event_date'].day == current_day_of_month:
                        event_name = events[index]['event_name']

                        event_status = events[index]['event_status']
                        event_status_cssclass = event_status
                        if day_in_future.date() < datetime.now().date():
                            event_status_cssclass = "past"
                            event_status = "Passed"
                        calendarhtml += "<div class='calendar-grid-event-name'>%s</div>" % event_name
                        calendarhtml += "<a href='/events/%s' class='calendar-grid-event-btn %s'>%s</a>" % (
                            events[index]['event_date'],
                            event_status_cssclass, event_status.capitalize())

        calendarhtml += "</div></div>"

    return calendarhtml


def get_user_display_name(request):
    """
    Function to display the correct battletag in the top right of all the views
    """
    if request.user.is_superuser:
        return 'God'
    if request.user.is_authenticated:
        if request.user.is_anonymous:
            user = 'Anonymous'
        else:
            user = get_current_user_data(request)['battletag']
    else:
        user = ''
    return user


def get_current_user_data(request):
    return SocialAccount.objects.get(user=request.user).extra_data


def get_user_chars_in_roster(request):
    try:
        res = Roster.objects.filter(
            account_id=get_current_user_data(request)['id'])
    except Roster.DoesNotExist:
        pass
    else:
        return res


def decline_raid_button(request, event_date):
    """
    removes all characters belonging to the currently logged-in user and remove them from the initial roster
    sent in the event/details view. Also removes the user from Late list if it exists.
    """
    event_obj = RaidEvent.objects.get(date=event_date)
    user_chars = get_user_chars_per_event(event_obj, request)
    for boss in user_chars.keys():
        if user_chars[boss]:
            boss_obj = BossPerEvent.objects.get(
                raid_event=event_obj, boss=Boss.objects.get(boss_id=boss))
            role = user_chars[boss]['role']
            name = user_chars[boss]['name']
            boss_obj.remove_from_role(role, name)

    AbsentUser.objects.update_or_create(user=MyUser.objects.get(user=request.user),
                                        raid_event=event_obj,
                                        account_id=get_current_user_data(request)['id'])

    remove_late_user(request, event_obj)

    return redirect('events')


def remove_late_user(request, event_obj):
    late_user_obj = LateUser.objects.filter(raid_event=event_obj, user=MyUser.objects.get(user=request.user))
    if late_user_obj.exists():
        late_user_obj.delete()


def attend_raid_button(request, event_date):
    """Current user can sign himself back in, if signed off before."""
    event_obj = RaidEvent.objects.get(date=event_date)
    result = AbsentUser.objects.get(user=MyUser.objects.get(
        user=request.user), raid_event=event_obj)
    result.delete()

    return redirect('events')


def roster_update_button(request):
    if check_token_life(request):
        return redirect('login-user-button')

    api_roster = get_guild_roster(request)
    populate_roster_db(api_roster)
    sync_roster_from_user_characters()
    return redirect('home')


def delete_event_button(request, event_date):
    """
    Deletes an event in the /events page and redirects back to the same page
    """
    event_obj = RaidEvent.objects.get(date=event_date)
    if request.user.is_staff:
        event_obj.delete()
        return redirect('events')
    else:
        return redirect('events')


def get_past_events():
    events = RaidEvent.objects.all().order_by('-date')
    past_events = []
    if events.exists():
        for event in events:
            if event.date < datetime.now().date():
                past_events.append(event)
    return past_events


def get_upcoming_events():
    events = RaidEvent.objects.all().order_by('date')
    upcoming_events = []
    if events.exists():
        for event in events:
            if event.date >= datetime.now().date():
                upcoming_events.append(event)
    return upcoming_events


def get_events():
    events = RaidEvent.objects.all().order_by('date')
    if events.exists():
        return events
    else:
        return None


def get_next_raid(current_raid):
    events = get_events()
    for i, event in enumerate(events):
        if event == current_raid and i != len(events) - 1:
            return events[i + 1]
    return current_raid


def get_previous_raid(current_raid):
    events = get_events()
    for i, event in enumerate(events):
        if event == current_raid and i != 0:
            return events[i - 1]
    return current_raid


def logout_user_button():
    return redirect('/accounts/logout/')


def login_user_button(request):
    return redirect('/accounts/battlenet/login/?process=login')


def handle_event_ajax(request, ajax_data):
    """
    Events takes 3 types of ajax request: late and decline.
    Call different functions depending on which one is specified in type
    """
    if ajax_data.get('type') is not None:
        if ajax_data.get('type') == 'decline':
            decline_raid_button(request, ajax_data.get('date'))

        elif ajax_data.get('type') == 'attend':
            attend_raid_button(request, ajax_data.get('date'))

        elif ajax_data.get('type') == 'late':
            save_late_user(request, ajax_data)


def save_late_user(request, ajax_data):
    """
    Reacts to ajax get request from event view. Minutes late gets stored into db after the button is pressed and
    submitted.
    """
    if ajax_data.get('date') is not None:
        date = ajax_data.get('date')
        minutes_late = ajax_data.get('minutes_late')
        current_raid = RaidEvent.objects.get(date=date)
        try:
            late_user_obj = LateUser.objects.get(user=MyUser.objects.get(user=request.user), raid_event=current_raid)
            if ajax_data.get('delete') == 'True':
                return late_user_obj.delete()

        except LateUser.DoesNotExist:
            LateUser.objects.create(raid_event=current_raid,
                                    minutes_late=minutes_late,
                                    user=MyUser.objects.get(user=request.user))
        else:
            LateUser.objects.filter(raid_event=current_raid, user=MyUser.objects.get(user=request.user)).update(minutes_late=minutes_late)


def publish_boss_ajax(ajax_data, current_raid):
    if ajax_data.get('publish') is not None and ajax_data.get('boss_id') is not None:
        boss_id = ajax_data.get('boss_id')
        publish = ajax_data.get('publish')
        boss = Boss.objects.get(boss_id=boss_id)
        BossPerEvent.objects.filter(
            boss=boss, raid_event=current_raid).update(published=publish)


def publish_event_ajax(ajax_data, current_raid):
    if ajax_data.get('publish') is not None and ajax_data.get('type') is not None:
        if ajax_data.get('type') == 'publish_event':
            publish = ajax_data.get('publish')
            BossPerEvent.objects.filter(
                raid_event=current_raid).update(published=publish)


def select_player_ajax(ajax_data, current_raid):
    """
    Overarching function that takes in the ajax request when a role button is clicked in frontend.
    If no roster exists for that particular boss on that date, a new object will be created or otherwise updated.
    After creating/updating the object, the update_selected_roster method is called to update the selected player in
    the database.
    """
    if ajax_data.get('name') is not None:
        role = ajax_data.get('role')
        name = ajax_data.get('name')
        boss_id = ajax_data.get('boss_id')
        boss = Boss.objects.get(boss_id=boss_id)

        boss_obj = BossPerEvent.objects.update_or_create(
            boss=boss, raid_event=current_raid)
        update_selected_roster(boss_obj, name, role)


def update_selected_roster(boss, name, role):
    """
    Upon clicking a tank/healer/melee/ranged icon while creating the active roster for a boss in the front end,
    the database will be updated with the selected player name and will either be removed or added.
    """
    boss = boss[0]
    if boss.check_exists(role, name):
        boss.remove_from_role(role, name)
    else:
        boss.add_to_role(role, name)


def create_roster_dict(current_raid):
    """
    Creates a json dictionary containing the default roster (everyone) and class except players that have signed off
    """
    roster_dict = {}
    roster = Roster.objects.all()

    # List Comprehension https://realpython.com/list-comprehension-python/
    # >>> sentence = 'the rocket came back from mars'
    # >>> vowels = [i for i in sentence if i in 'aeiou']
    # >>> vowels
    # ['e', 'o', 'e', 'a', 'e', 'a', 'o', 'a']

    absent_user_list = [
        user.account_id for user in AbsentUser.objects.filter(raid_event=current_raid)]
    roster_list = [
        char.name for char in roster if char.account_id not in absent_user_list]

    for character in roster:
        if character.playable_class is not None:
            if character.name in roster_list:
                wishes = BossWishes.objects.filter(
                    character_id=character.character_id).only('wishes')
                roster_dict[character.id] = {
                    'name': character.name,
                    'playable_class': character.playable_class,
                    'account_id': character.account_id if character.account_id is not None else "",
                    'wishes': serializers.serialize("json", wishes),
                }
    return roster_dict


def selected_roster_from_db_to_json(current_raid):
    """
    Queries all selected players corresponding to all bosses in a single event date and pushes them to a
    json file that serves as context in the event-details view
    """
    boss_roster = BossPerEvent.objects.filter(raid_event=current_raid)

    roster = {}
    for boss in boss_roster:
        boss_id = boss.boss.boss_id
        roster[boss_id] = {}

        roster[boss_id]['published'] = str(boss.published)
        roster[boss_id]['tank'] = [char.name for char in boss.tank.all()]
        roster[boss_id]['healer'] = [char.name for char in boss.healer.all()]
        roster[boss_id]['rdps'] = [char.name for char in boss.rdps.all()]
        roster[boss_id]['mdps'] = [char.name for char in boss.mdps.all()]

    return roster


def user_attendance_status(event, request):
    if not is_raider(request):
        return 'Click For Details'

    user = get_current_user_data(request)['id']
    if AbsentUser.objects.filter(raid_event=event, account_id=user).exists():
        return 'absent'

    boss_obj = BossPerEvent.objects.filter(raid_event=event)
    if not boss_obj.exists():
        return 'Pending'

    if not event.event_is_published():
        return "Pending"

    for user_char in get_user_chars_in_roster(request):
        for boss in BossPerEvent.objects.filter(raid_event=event):
            roles = ['tank', 'healer', 'rdps', 'mdps']
            for role in roles:
                if boss.check_exists(role, user_char):
                    return 'selected'

    for boss in boss_obj:
        total_roster_count = boss.tank.count() + boss.healer.count() + \
            boss.rdps.count() + boss.mdps.count()
        if 0 < total_roster_count < 20:
            return 'Pending'

    return 'benched'


def sync_bnet(request):
    """
    If new user logs in via battlenet, their characters will be fetched by API and
    their class and account_id will be linked in Roster. Officers will be added to a django admin group and
    given staff status.
    """
    if check_token_life(request):
        return redirect('login-user-button')

    all_user_characters = get_user_profile_data(request)
    populate_user_characters(all_user_characters)
    set_account_id_and_class(all_user_characters)
    set_officer_staff(request)
    return redirect('home')


def check_token_life(request):
    acc = SocialAccount.objects.get(user=request.user)
    token_expiration_date = SocialToken.objects.get(account=acc).expires_at
    dt = datetime.now()
    dt = dt.replace(tzinfo=timezone.utc)
    if token_expiration_date < dt:
        return True


def set_officer_staff(request):
    account_id = get_current_user_data(request)['id']
    officer_ranks = [0, 1]
    try:
        user_characters = Roster.objects.filter(account_id=account_id)
    except Roster.DoesNotExist:
        pass
    else:
        for character in user_characters:
            if character.rank in officer_ranks:
                group = Group.objects.get(name='Officers')
                request.user.groups.add(group)
                request.user.is_staff = True
                request.user.save()
                break


def toggle_staff_button(request):
    refererURL = request.META.get('HTTP_REFERER') or 'home'
    if request.user.is_staff:
        request.user.is_staff = False
        request.user.save()
        return redirect(refererURL)
    if not request.user.is_staff and is_user_officer(request):
        request.user.is_staff = True
        request.user.save()
        return redirect(refererURL)


def is_user_officer(request):
    if request.user.is_anonymous or request.user.is_superuser:
        return False
    if request.user.is_authenticated:
        account_id = get_current_user_data(request)['id']
        officer_ranks = [0, 1]
        user_characters = Roster.objects.filter(account_id=account_id)
        for character in user_characters:
            if character.rank in officer_ranks:
                return True
    return False


def load_roster_template(current_raid, ajax_data):
    if ajax_data.get('saved_setup') is not None:
        boss_id = ajax_data.get('boss_id')
        roster = json.loads(ajax_data.get('saved_setup'))

        boss_obj = Boss.objects.get(boss_id=boss_id)
        obj = BossPerEvent.objects.filter(
            raid_event=current_raid, boss=boss_obj)

        if obj.exists():
            obj.delete()

        obj = BossPerEvent.objects.create(
            boss=boss_obj, raid_event=current_raid)

        for character in roster:
            obj.add_to_role(character['role'], character['name'])


def get_user_chars_per_event(current_raid, request):
    if is_user_absent(current_raid, request):
        return {}
    obj = BossPerEvent.objects.filter(raid_event=current_raid)
    user_chars_selected_per_raid = {}
    for boss_obj in obj:
        id = boss_obj.boss.boss_id
        user_chars_selected_per_raid[id] = {}
        for char in get_user_chars_in_roster(request):
            if char in boss_obj.tank.all():
                user_chars_selected_per_raid[id] = {'name': char.name, 'playable_class': char.playable_class,
                                                    'role': 'tank'}
            if char in boss_obj.healer.all():
                user_chars_selected_per_raid[id] = {'name': char.name, 'playable_class': char.playable_class,
                                                    'role': 'healer'}
            if char in boss_obj.rdps.all():
                user_chars_selected_per_raid[id] = {'name': char.name, 'playable_class': char.playable_class,
                                                    'role': 'rdps'}
            if char in boss_obj.mdps.all():
                user_chars_selected_per_raid[id] = {'name': char.name, 'playable_class': char.playable_class,
                                                    'role': 'mdps'}
    return user_chars_selected_per_raid


def get_chars_by_account_id(account_id: int):
    return [char for char in Roster.objects.filter(account_id=account_id)]


def add_cssclass_to_roster_list(roster):
    playable_classes = get_playable_classes_as_css_classes()
    for char in roster:
        char.css_class = playable_classes.get(char.playable_class)
    return roster


def boss_object_to_list():
    return [{'name': boss.boss_name, 'id': boss.boss_id, 'visible': boss.boss_wishes_visible} for boss in Boss.objects.all().order_by('boss_id')]


def is_user_absent(event, request, account_id=0):
    account_id = get_current_user_data(
        request)['id'] if account_id == 0 else account_id
    if AbsentUser.objects.filter(raid_event=event, account_id=account_id).exists():
        return True
    else:
        return False


def is_raider(request):
    account_id = get_current_user_data(request)['id']
    if Roster.objects.filter(account_id=account_id).exists():
        return True
    else:
        return False


def user_btag_from_account_id(account_id):
    return SocialAccount.objects.get(uid=account_id).extra_data.get("battletag")


def get_declined_users_for_event(request, current_raid):
    """
    Returns a list of users declined for current raid.
    """
    declined_users = []
    absent_user = AbsentUser.objects.filter(raid_event=current_raid)
    for user in absent_user:
        character_name = Roster.objects.filter(
            account_id=user.account_id).first().name
        declined_users.append([user, character_name])
    return declined_users


def get_all_declined_users():
    res = AbsentUser.objects.all()
    declined_users = []
    for user in res:
        if user.user not in declined_users:
            declined_users.append(user.user)


def update_boss_wish_data(ajax_data):
    wishes = ajax_data.get('wishes')
    character_id = ajax_data.get('character_id')
    if wishes is not None and character_id is not None:
        try:
            BossWishes.objects.get(character_id=character_id)
        except BossWishes.DoesNotExist:
            BossWishes.objects.create(
                character_id=character_id,
                wishes=json.loads(wishes)
            )
        else:
            BossWishes.objects.filter(character_id=character_id).update(
                wishes=json.loads(wishes)
            )


def get_boss_wishes_by_account_id(account_id):
    user_chars = get_chars_by_account_id(account_id)
    wishes = []
    for char in user_chars:
        character_id = char.character_id
        char_wishes = BossWishes.objects.filter(
            character_id=character_id)
        if char_wishes.exists():
            wishes.append(char_wishes)
    return wishes


def get_all_bosswishes():
    all_chars = Roster.objects.all().order_by('playable_class')
    all_wishes = []
    playable_classes = get_playable_classes_as_css_classes()
    for char in all_chars:
        character_id = char.character_id
        try:
            char_wishes = BossWishes.objects.filter(character_id=character_id)
            if char_wishes.exists():
                for wish in char_wishes:
                    wish.css_class = playable_classes.get(char.playable_class)
                    wish.character_name = char.name
                    all_wishes.append(wish)
            else:
                mock_wishes = {boss.boss_id: '-'
                               for boss in Boss.objects.all().order_by('boss_id')}
                all_wishes.append({
                    'character_id': character_id,
                    'wishes': mock_wishes,
                    'css_class': playable_classes.get(char.playable_class),
                    'character_name': char.name,
                })
        except BossWishes.DoesNotExist as e:
            print(e)

    return all_wishes


def update_boss_visibility(ajax_data):
    visibility = ajax_data.get('visibility')
    if visibility is not None:
        visibility = json.loads(visibility)
        for boss in visibility.items():
            boss_id = boss[0]
            # Workaround to get the JS true/false as python bool
            visible = True if boss[1] == 'True' else False
            Boss.objects.filter(boss_id=boss_id).update(
                boss_wishes_visible=visible)
