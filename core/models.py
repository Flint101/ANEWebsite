import requests
from allauth.socialaccount.models import SocialAccount, SocialToken

from django.contrib.auth.models import User

from django.db import models
from django.db.models import Model


class Rank(models.IntegerChoices):
    GM = 0, 'GM'
    OFFICER = 1, "Officer"
    OFFICER_ALT = 2, "Officer Alt"
    RAIDER = 3, "Raider"
    SECOND_MAIN = 4, 'Second Main'
    TRIAL = 5, "Trial"


class Roster(models.Model):
    name = models.CharField(max_length=20, unique=True)
    rank = models.IntegerField(choices=Rank.choices)
    character_id = models.IntegerField(unique=True)
    account_id = models.IntegerField(default=0, blank=True)
    playable_class = models.CharField(max_length=50, null=True, blank=True)

    def __str__(self):
        return self.name


class Boss(models.Model):
    boss_name = models.CharField(max_length=50, null=True, blank=True)
    boss_id = models.IntegerField(null=True, blank=True, unique=True)
    boss_wishes_visible = models.BooleanField(default=False)

    def __str__(self):
        return self.boss_name


class MyUser(SocialAccount):
    class Meta:
        proxy = True

    def __str__(self):
        return self.extra_data['battletag']


class RaidEvent(models.Model):
    name = models.CharField(max_length=30, default='Raid')
    date = models.DateField(unique=True)
    rosterFK = models.ForeignKey(
        Roster, blank=True, default=True, related_name='roster', on_delete=models.CASCADE)
    roster = Roster.objects.prefetch_related('roster')
    bosses = models.ManyToManyField(Boss, through='BossPerEvent')
    late = models.ManyToManyField(
        MyUser, through='LateUser', related_name='late_user')
    absent = models.ManyToManyField(
        MyUser, through='AbsentUser', related_name='absent_user')

    def __str__(self):
        return str(self.date)

    def event_is_published(self):
        bosses = BossPerEvent.objects.filter(raid_event=self)
        if not bosses.exists():
            return False

        published_bosses = 0
        for boss in bosses:
            if boss.published:
                published_bosses += 1
        if published_bosses == 0:
            return False
        return True


class LateUser(models.Model):
    user = models.ForeignKey(MyUser, on_delete=models.CASCADE)
    raid_event = models.ForeignKey(
        RaidEvent, on_delete=models.CASCADE, null=True)
    minutes_late = models.CharField(max_length=20)

    def __str__(self):
        return str(self.user.extra_data['battletag'])

    def date(self):
        return str(self.raid_event.date)


class AbsentUser(models.Model):
    user = models.ForeignKey(MyUser, on_delete=models.CASCADE)
    account_id = models.IntegerField(default=0)
    raid_event = models.ForeignKey(
        RaidEvent, on_delete=models.CASCADE, null=True)

    def __str__(self):
        return str(self.user.extra_data['battletag'])

    def date(self):
        return str(self.raid_event.date)


class BossPerEvent(models.Model):
    boss = models.ForeignKey(Boss, on_delete=models.CASCADE, null=True)
    raid_event = models.ForeignKey(
        RaidEvent, on_delete=models.CASCADE, null=True)
    tank = models.ManyToManyField(Roster, blank=True, related_name='rel_tank')
    healer = models.ManyToManyField(
        Roster, blank=True, related_name='rel_healer')
    mdps = models.ManyToManyField(Roster, blank=True, related_name='rel_mdps')
    rdps = models.ManyToManyField(Roster, blank=True, related_name='rel_rdps')
    published = models.BooleanField(default=False)

    def __str__(self):
        return str(self.boss.boss_name)

    def dateDisplay(self):
        return str(self.raid_event.date)

    def bossDisplay(self):
        return str(self.boss.boss_name)

    def check_exists(self, role, name):
        return getattr(self, role).filter(name=name).exists()

    def add_to_role(self, role, name):
        getattr(self, role).add(Roster.objects.get(name=name))

    def remove_from_role(self, role, name):
        getattr(self, role).remove(Roster.objects.get(name=name))


class UserCharacters(models.Model):
    name = models.CharField(max_length=30)
    character_id = models.IntegerField(unique=True)
    account_id = models.IntegerField()
    playable_class = models.CharField(max_length=30)


class BossWishes(models.Model):
    character_id = models.IntegerField(unique=True, blank=True)
    wishes = models.JSONField()


def set_account_id_and_class(char_json):
    """
    Updates the account id and playable class in the Roster with the data received from the API after someone logs in
    """
    for i in range(len(char_json['wow_accounts'])):
        for j in range(len(char_json['wow_accounts'][i]['characters'])):
            account_id = char_json['id']
            playable_class = char_json['wow_accounts'][i]['characters'][j]['playable_class']['name']
            char_id = char_json['wow_accounts'][i]['characters'][j]['id']
            try:
                res = Roster.objects.get(character_id=char_id)
            except Roster.DoesNotExist:
                pass
            else:
                res.account_id = account_id
                res.playable_class = playable_class
                res.save()


def sync_roster_from_user_characters():
    unsynced = Roster.objects.filter(account_id__isnull=True)
    for character in unsynced:
        if UserCharacters.objects.filter(character_id=character.character_id).exists():
            character.account_id = UserCharacters.objects.get(
                character_id=character.character_id).account_id
            character.playable_class = UserCharacters.objects.get(
                character_id=character.character_id).playable_class
            character.save()


def populate_user_characters(char_json):
    for i in range(len(char_json['wow_accounts'])):
        for j in range(len(char_json['wow_accounts'][i]['characters'])):
            if char_json['wow_accounts'][i]['characters'][j]['realm']['id'] == 1306:
                account_id = char_json['id']
                char_name = char_json['wow_accounts'][i]['characters'][j]['name']
                playable_class = char_json['wow_accounts'][i]['characters'][j]['playable_class']['name']
                char_id = char_json['wow_accounts'][i]['characters'][j]['id']
                UserCharacters.objects.filter(character_id=char_id).update_or_create(account_id=account_id,
                                                                                     name=char_name,
                                                                                     playable_class=playable_class,
                                                                                     character_id=char_id)


def get_user_profile_data(request):
    """
    API calls to the blizzard endpoint that returns all
    characters that belong to the logged-in user
    """
    current_user = SocialAccount.objects.get(user=request.user)
    access_token = SocialToken.objects.get(account=current_user)
    header = {
        'Authorization': 'Bearer %s' % access_token,
    }
    response = requests.get('https://eu.api.blizzard.com/profile/user/wow?namespace=profile-eu&locale=en_US',
                            headers=header)

    result = response.json()
    return result


def populate_roster_db(api_roster):
    """
    Adding characters from the API call that contains all guild roster characters and filters them by rank
    """
    raider_ranks = [0, 1, 3, 4, 5]
    for member in api_roster['members']:
        rank = member['rank']
        name = member['character']['name']
        character_id = member['character']['id']
        if rank in raider_ranks:
            try:
                Roster.objects.get(name=name)
            except Roster.DoesNotExist:
                Roster.objects.create(
                    name=name, rank=rank, character_id=character_id)
            else:
                Roster.objects.filter(name=name).update(rank=rank,
                                                        character_id=character_id)
        else:
            demoted_player = Roster.objects.filter(name=name)
            demoted_player.delete()


def get_guild_roster(request):
    """
    API calls to the blizzard endpoint that returns all
    characters that exist in A Necessary Evil
"""
    current_user = SocialAccount.objects.get(user=request.user)
    access_token = SocialToken.objects.get(account=current_user)
    header = {
        'Authorization': 'Bearer %s' % access_token,
    }
    response = requests.get(
        'https://eu.api.blizzard.com/data/wow/guild/tarren-mill/a-necessary-evil/roster?namespace=profile-eu&locale=en_US',
        headers=header)
    result = response.json()
    return result
