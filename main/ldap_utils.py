import ldap


def ldap_auth(username, password):
    """
    Direkte LDAP Authentifizierung ohne Django Backend
    Für erweiterte Kontrolle über den LDAP Login
    """
    try:
        from django.conf import settings
        import ldap
        
        # LDAP Verbindung herstellen
        conn = ldap.initialize(settings.AUTH_LDAP_SERVER_URI)
        conn.set_option(ldap.OPT_REFERRALS, 0)
        
        # Benutzer-DN finden
        search_filter = settings.AUTH_LDAP_USER_SEARCH.filterstr % {'user': username}
        result = conn.search_s(
            settings.AUTH_LDAP_USER_SEARCH.search_base,
            ldap.SCOPE_SUBTREE,
            search_filter,
            ['dn']
        )
        
        if not result:
            return None
        
        user_dn = result[0][0]
        
        # Versuche Bind mit Benutzer-Credentials
        conn.simple_bind_s(user_dn, password)
        
        # Authentifizierung erfolgreich
        conn.unbind()
        return True
        
    except ldap.INVALID_CREDENTIALS:
        return False
    except ldap.LDAPError as e:
        print(f"LDAP Error: {e}")
        return False
    except Exception as e:
        print(f"General Error: {e}")
        return False

def ldap_user_info(username, password):
    """
    Holt Benutzerinformationen direkt aus LDAP
    """
    try:
        from django.conf import settings
        import ldap
        
        conn = ldap.initialize(settings.AUTH_LDAP_SERVER_URI)
        conn.set_option(ldap.OPT_REFERRALS, 0)
        
        # Mit Admin Account binden um Benutzerdaten zu lesen
        conn.simple_bind_s(settings.AUTH_LDAP_BIND_DN, settings.AUTH_LDAP_BIND_PASSWORD)
        
        # Benutzer suchen
        search_filter = settings.AUTH_LDAP_USER_SEARCH.filterstr % {'user': username}
        result = conn.search_s(
            settings.AUTH_LDAP_USER_SEARCH.search_base,
            ldap.SCOPE_SUBTREE,
            search_filter,
            ['givenName', 'sn', 'mail', 'uid', 'cn']
        )
        
        if not result:
            return None
        
        user_data = {
            'dn': result[0][0],
            'attributes': {}
        }
        
        for attr_name, attr_value in result[0][1].items():
            if attr_value:
                user_data['attributes'][attr_name] = [
                    value.decode('utf-8') if isinstance(value, bytes) else value 
                    for value in attr_value
                ]
        
        conn.unbind()
        return user_data
        
    except Exception as e:
        print(f"LDAP User Info Error: {e}")
        return None
    
