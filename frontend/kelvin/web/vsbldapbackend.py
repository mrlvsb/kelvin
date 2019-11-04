from django.contrib.auth.backends import BaseBackend

from django.contrib.auth.models import User

import ldap

# Django LDAP package (inspiration for multple atttempts)
# https://django-auth-ldap.readthedocs.io/en/latest/custombehavior.html

# Auth backend: https://docs.djangoproject.com/en/3.0/topics/auth/customizing/
# Auth backend reference: https://docs.djangoproject.com/en/3.0/ref/contrib/auth/#authentication-backends-reference


def ldap_auth(username, password):
    ldap.set_option(ldap.OPT_REFERRALS,0)
    ldap.protocol_version = 3

    ldap_server='ldaps://ldap.vsb.cz'

    # VSB specific user context
    trailing_context = username[-1]

    # the following is the user_dn format provided by the ldap server
    user_dn = 'cn=' + username

    # adjust this to your base dn for searching
    base_dn = 'ou=USERS,o=VSB'

    connect = ldap.initialize(ldap_server)
    search_filter = 'cn=' + username

    listing = connect.search_s(base_dn, ldap.SCOPE_SUBTREE, user_dn, [])

    if len(listing) == 0:
        print('User not found')
        return False
    else:

        #connect.set_option(ldap.OPT_REFERRALS, 0)
        try:
            #if authentication successful, get the full user data
            connect.simple_bind_s('cn={},ou={},ou=USERS,o=VSB'.format(username, trailing_context), password)
            result = connect.search_s(base_dn, ldap.SCOPE_SUBTREE, search_filter)

            # return all user data results
            connect.unbind_s()
            return True
        except ldap.LDAPError as e:
            connect.unbind_s()
            print('authentication error')
            return False


class MyLDAPBackend(BaseBackend):
    default_settings = {
        "LOGIN_COUNTER_KEY": "CUSTOM_LDAP_LOGIN_ATTEMPT_COUNT",
        "LOGIN_ATTEMPT_LIMIT": 50,
        "RESET_TIME": 30 * 60,
        "USERNAME_REGEX": r"^.*$",
    }

    def authenticate(self, request, username=None, password=None):
        
        authenticated = ldap_auth(username, password)

        #user = ldap_user.authenticate(password)
        #if user and self.username_matches_regex(user.username):
        #    self.send_sms(user.username)
        #return user
        if authenticated:
            user = User.objects.get(username=username)
            return user
        else:
            return None

    def get_user(self, user_id):
        try:
            return User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return None



