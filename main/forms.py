from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib.auth.models import User
from captcha.fields import CaptchaField

class CustomUserCreationForm(UserCreationForm):
    email = forms.EmailField(required=True, label='E-Mail')
    first_name = forms.CharField(max_length=30, required=True, label='Vorname')
    last_name = forms.CharField(max_length=30, required=True, label='Nachname')

    class Meta:
        model = User
        fields = ('username', 'first_name', 'last_name', 'email', 'password1', 'password2')

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        user.first_name = self.cleaned_data['first_name']
        user.last_name = self.cleaned_data['last_name']
        if commit:
            user.save()
        return user

class LdapAuthenticationForm(forms.Form):
    """
    LDAP-only Login Form ohne lokale User-Prüfung
    """    
    username = forms.CharField(
        label='Benutzername',
        widget=forms.TextInput(attrs={
            'class': 'form-control', 
            'placeholder': 'Benutzername',
            'autofocus': True
        })
    )
    password = forms.CharField(
        label='Passwort',
        widget=forms.PasswordInput(attrs={
            'class': 'form-control', 
            'placeholder': 'Passwort'
        })
    )
    
    def __init__(self, request=None, *args, **kwargs):
        """
        Request parameter wird ignoriert - wir brauchen keine Session-Info
        """
        super().__init__(*args, **kwargs)
        self.request = request

    def clean(self):
        """
        Deaktiviere die Standard-Clean-Methodik
        Wir validieren nur im LDAP, nicht lokal
        """
        cleaned_data = super().clean()
        username = cleaned_data.get('username')
        password = cleaned_data.get('password')
        
        # Basis-Validierung
        if not username or not password:
            raise forms.ValidationError(
                "Bitte Benutzername und Passwort eingeben.",
                code='missing_credentials'
            )
        
        return cleaned_data

class UserProfileForm(forms.ModelForm):

    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email']
        labels = {
            'first_name': 'Vorname',
            'last_name': 'Nachname',
            'email': 'E-Mail',
        }
        widgets = {
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
        }


class PasswordResetRequestForm(forms.Form):
    """
    Formular für Passwort-Reset-Anfrage
    Benutzer gibt Email oder Benutzername ein
    """
    captcha = CaptchaField(
        label='Sicherheitscode',
        error_messages={
            'invalid': 'Der eingegebene Sicherheitscode ist falsch. Bitte versuchen Sie es erneut.'
        }
    )

    identifier = forms.CharField(
        label='Benutzername oder E-Mail',
        max_length=254,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Ihr Benutzername oder E-Mail-Adresse',
            'autofocus': True
        }),
        help_text='Geben Sie Ihren Benutzernamen oder Ihre E-Mail-Adresse ein'
    )

    def clean_identifier(self):
        """
        Validiert ob ein Benutzer mit diesem Identifier existiert
        Sucht nach: Benutzername, Organisations-E-Mail, private E-Mail (mailRoutingAddress)
        """
        identifier = self.cleaned_data['identifier']

        # Suche Benutzer nach Benutzername oder Email
        user = None
        try:
            # Erst nach Benutzername suchen
            user = User.objects.get(username=identifier)
        except User.DoesNotExist:
            # Dann nach Organisations-Email suchen
            try:
                user = User.objects.get(email=identifier)
            except User.DoesNotExist:
                pass
            except User.MultipleObjectsReturned:
                user = User.objects.filter(email=identifier).order_by('date_joined').first()

        # Falls nicht gefunden: LDAP nach mailRoutingAddress durchsuchen
        if not user:
            try:
                from main.ldap_manager import LDAPManager
                with LDAPManager() as ldap:
                    results = ldap.conn.search_s(
                        ldap.user_search_base,
                        2,  # SCOPE_SUBTREE
                        f'(mailRoutingAddress={identifier})',
                        ['cn']
                    )
                    if results:
                        dn, attrs = results[0]
                        cn = attrs.get('cn', [b''])[0]
                        if isinstance(cn, bytes):
                            cn = cn.decode('utf-8')
                        if cn:
                            try:
                                user = User.objects.get(username=cn)
                            except User.DoesNotExist:
                                pass
            except Exception:
                pass

        # Speichere gefundenen User für später
        self.user = user

        return identifier


class PasswordResetConfirmForm(forms.Form):
    """
    Formular zum Setzen des neuen Passworts
    """
    new_password1 = forms.CharField(
        label='Neues Passwort',
        strip=False,
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Neues Passwort',
            'autocomplete': 'new-password',
            'autofocus': True
        }),
        help_text='Mindestens 8 Zeichen'
    )
    new_password2 = forms.CharField(
        label='Passwort bestätigen',
        strip=False,
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Passwort wiederholen',
            'autocomplete': 'new-password'
        })
    )

    def clean_new_password1(self):
        """Validiere Passwort-Stärke"""
        password = self.cleaned_data.get('new_password1')

        if len(password) < 8:
            raise forms.ValidationError(
                'Das Passwort muss mindestens 8 Zeichen lang sein.',
                code='password_too_short'
            )

        return password

    def clean(self):
        """Prüfe ob beide Passwörter übereinstimmen"""
        cleaned_data = super().clean()
        password1 = cleaned_data.get('new_password1')
        password2 = cleaned_data.get('new_password2')

        if password1 and password2:
            if password1 != password2:
                raise forms.ValidationError(
                    'Die beiden Passwörter stimmen nicht überein.',
                    code='password_mismatch'
                )

        return cleaned_data