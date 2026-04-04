"""
Tests fuer Django-Models (ohne LDAP-Verbindung)
"""
from django.test import TestCase
from django.contrib.auth.models import User

from authapp.models import AppSettings, PermissionMapping
from mailing.models import MailCampaign, MailTemplate
from privacy.models import PrivacyPolicy, ConsentLog, DeletionRequest
from tickets.models import Ticket, TicketComment


class AppSettingsTest(TestCase):
    def test_get_default(self):
        self.assertEqual(AppSettings.get('nonexistent', 'fallback'), 'fallback')

    def test_set_and_get(self):
        AppSettings.set('test_key', 'test_value', 'general', 'Test')
        self.assertEqual(AppSettings.get('test_key'), 'test_value')

    def test_update(self):
        AppSettings.set('key1', 'old')
        AppSettings.set('key1', 'new')
        self.assertEqual(AppSettings.get('key1'), 'new')


class PermissionMappingTest(TestCase):
    def test_get_groups_empty(self):
        groups = PermissionMapping.get_groups_for_permission('nonexistent')
        self.assertEqual(groups, [])

    def test_permission_choices_not_empty(self):
        self.assertTrue(len(PermissionMapping.PERMISSION_CHOICES) > 0)

    def test_send_massmail_in_choices(self):
        keys = [k for k, _ in PermissionMapping.PERMISSION_CHOICES]
        self.assertIn('send_massmail', keys)


class MailCampaignTest(TestCase):
    def test_create(self):
        c = MailCampaign.objects.create(subject='Test', body_html='<p>Hallo</p>')
        self.assertEqual(str(c), 'Test (Entwurf)')
        self.assertEqual(c.status, 'draft')

    def test_recipient_type_default(self):
        c = MailCampaign.objects.create(subject='Test', body_html='')
        self.assertEqual(c.recipient_type, 'members')


class MailTemplateTest(TestCase):
    def test_create(self):
        t = MailTemplate.objects.create(name='Test', subject='Betreff', body_html='<p>Hi</p>')
        self.assertEqual(str(t), 'Test')


class ConsentLogTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('testuser', 'test@test.de', 'pass')

    def test_opt_out_default_granted(self):
        """Opt-out: Wenn kein Consent existiert, gilt als erteilt"""
        latest = ConsentLog.objects.filter(user=self.user, consent_type='email_communication').first()
        self.assertIsNone(latest)  # Kein Eintrag = erteilt (Opt-out)

    def test_revoke(self):
        ConsentLog.objects.create(user=self.user, consent_type='email_communication', granted=False)
        latest = ConsentLog.objects.filter(user=self.user, consent_type='email_communication').order_by('-timestamp').first()
        self.assertFalse(latest.granted)


class PrivacyPolicyTest(TestCase):
    def test_get_active_none(self):
        self.assertIsNone(PrivacyPolicy.get_active())

    def test_get_active(self):
        PrivacyPolicy.objects.create(version='1.0', title='Test', content_html='<p>Test</p>', is_active=True)
        self.assertIsNotNone(PrivacyPolicy.get_active())

    def test_only_one_active(self):
        p1 = PrivacyPolicy.objects.create(version='1.0', title='V1', content_html='', is_active=True)
        p2 = PrivacyPolicy.objects.create(version='2.0', title='V2', content_html='', is_active=True)
        p1.refresh_from_db()
        self.assertFalse(p1.is_active)
        self.assertTrue(p2.is_active)


class TicketTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('testuser', 'test@test.de', 'pass')

    def test_create(self):
        t = Ticket.objects.create(title='Bug', description='Broken', created_by=self.user)
        self.assertEqual(t.status, 'open')
        self.assertEqual(t.priority, 'medium')
        self.assertEqual(str(t), f'#{t.pk} Bug')

    def test_comment(self):
        t = Ticket.objects.create(title='Test', description='', created_by=self.user)
        TicketComment.objects.create(ticket=t, author=self.user, content='Fix kommt')
        self.assertEqual(t.comments.count(), 1)

    def test_type_icon(self):
        t = Ticket(ticket_type='bug')
        self.assertEqual(t.type_icon, 'bi-bug')
