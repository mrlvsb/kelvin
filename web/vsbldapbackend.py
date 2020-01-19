import ldap

from django.contrib.auth.backends import ModelBackend
from django.contrib.auth.models import User


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


class MyLDAPBackend(ModelBackend):
    def authenticate(self, request, username=None, password=None):
        if not username or not password:
            return None

        username = username.upper()
        try:
            authenticated = ldap_auth(username, password)
            if authenticated:
                return User.objects.get(username=username)
        except User.DoesNotExist:
            pass

        return None
