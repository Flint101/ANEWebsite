import requests
from allauth.socialaccount.models import SocialAccount, SocialToken
from django.contrib.auth.models import User
from django.contrib.auth.signals import user_logged_in
from django.db import models, IntegrityError
from django.dispatch import receiver


class Rank(models.IntegerChoices):
    GM = 0, 'GM'
    OFFICER = 1, "Officer"
    OFFICER_ALT = 2, "Officer Alt"
    RAIDER = 3, "Raider"
    SECOND_MAIN = 4, 'Second Main'
    TRIAL = 5, "Trial"


class CurrentUser(models.Model):
    account_id = models.IntegerField()
    character_id = models.IntegerField(unique=True)
    name = models.CharField(max_length=20)
    rank = models.IntegerField(choices=Rank.choices, null=True)

    def __str__(self):
        return self.name


class Roster(models.Model):
    name = models.CharField(max_length=20, unique=True)
    rank = models.IntegerField(choices=Rank.choices)
    character_id = models.IntegerField(unique=True)
    in_raid = models.BooleanField(default=True)

    def __str__(self):
        return self.name


class RaidBosses(models.Model):
    boss_name = models.CharField(max_length=50, null=True, blank=True)

    def __str__(self):
        return self.boss_name


class RaidInstance(models.Model):
    name = models.CharField(max_length=40, null=True)
    bosses = models.ManyToManyField(RaidBosses, blank=True)

    def __str__(self):
        return self.name


class RaidEvent(models.Model):
    name = models.CharField(max_length=30, default='Raid')
    date = models.DateField(unique=True)
    roster = models.ManyToManyField(Roster, blank=True, default=True)

    def populate_roster(self):
        for character in Roster.objects.all():
            self.roster.add(Roster.objects.get(name=character))

    def remove_char_from_roster(self, current_user_id):
        user_chars_in_roster = get_chars_in_roster(current_user_id)
        for item in user_chars_in_roster:
            self.roster.remove(Roster.objects.get(name=item))
            self.save()

    def sign_in(self, current_user_id):
        user_chars_in_roster = get_chars_in_roster(current_user_id)
        for item in user_chars_in_roster:
            self.roster.add(Roster.objects.get(name=item))
            self.save()


def get_chars_in_roster(current_user_id):
    roster = []
    for character in Roster.objects.all():
        roster.append(character.name)
    user_chars = []
    for character in CurrentUser.objects.filter(account_id=current_user_id):
        user_chars.append(character.name)
    user_chars_in_roster = set(roster).intersection(set(user_chars))
    return user_chars_in_roster


@receiver(user_logged_in)
def post_login(sender, user, request, **kwargs):
    account_id = SocialAccount.objects.get(user=request.user).extra_data['id']
    if not CurrentUser.objects.filter(account_id=account_id).exists():
        api_profiles = get_profile_summary(request)
        populate_char_db(api_profiles)


def populate_char_db(char_json):
    for i in range(len(char_json['wow_accounts'])):
        for j in range(len(char_json['wow_accounts'][i]['characters'])):
            realm_id = char_json['wow_accounts'][i]['characters'][j]['realm']['id']
            character_level = char_json['wow_accounts'][i]['characters'][j]['level']
            if realm_id == 1306 and character_level == 60:  #tarrenmill
                account_id = char_json['id']
                char_name = char_json['wow_accounts'][i]['characters'][j]['name']
                char_id = char_json['wow_accounts'][i]['characters'][j]['id']

                try:
                    CurrentUser.objects.update_or_create(name=char_name, account_id=account_id, character_id=char_id, rank='7')
                except IntegrityError:
                    pass


def get_profile_summary(request):
    current_user = SocialAccount.objects.filter(user=request.user).first()
    access_token = SocialToken.objects.filter(account=current_user).first()
    header = {
        'Authorization': 'Bearer %s' % access_token,
    }
    response = requests.get('https://eu.api.blizzard.com/profile/user/wow?namespace=profile-eu&locale=en_US',
                            headers=header)

    result = response.json()
    return result