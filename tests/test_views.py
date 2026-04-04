"""
Tests fuer Views (ohne LDAP - nur Django-seitige Logik)
"""
from django.test import TestCase, Client
from django.contrib.auth.models import User


class PublicViewsTest(TestCase):
    """Views die ohne Login erreichbar sein muessen"""

    def test_login_page(self):
        r = self.client.get('/login/')
        self.assertEqual(r.status_code, 200)

    def test_register_page(self):
        r = self.client.get('/register/')
        self.assertEqual(r.status_code, 200)

    def test_privacy_policy(self):
        r = self.client.get('/datenschutz/')
        self.assertEqual(r.status_code, 200)

    def test_impressum(self):
        r = self.client.get('/datenschutz/impressum/')
        self.assertEqual(r.status_code, 200)

    def test_cookies(self):
        r = self.client.get('/datenschutz/cookies/')
        self.assertEqual(r.status_code, 200)

    def test_password_reset(self):
        r = self.client.get('/password-reset/')
        self.assertEqual(r.status_code, 200)


class AuthRequiredViewsTest(TestCase):
    """Views die Login erfordern -> Redirect auf Login"""

    def test_dashboard_redirect(self):
        r = self.client.get('/dashboard/')
        self.assertEqual(r.status_code, 302)
        self.assertIn('/login/', r.url)

    def test_profile_redirect(self):
        r = self.client.get('/profile/')
        self.assertEqual(r.status_code, 302)

    def test_tickets_redirect(self):
        r = self.client.get('/tickets/')
        self.assertEqual(r.status_code, 302)

    def test_my_data_redirect(self):
        r = self.client.get('/datenschutz/my-data/')
        self.assertEqual(r.status_code, 302)


class TicketViewsTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('testuser', 'test@test.de', 'pass')
        self.client.login(username='testuser', password='pass')

    def test_ticket_list(self):
        r = self.client.get('/tickets/')
        self.assertEqual(r.status_code, 200)

    def test_ticket_create_page(self):
        r = self.client.get('/tickets/new/')
        self.assertEqual(r.status_code, 200)

    def test_ticket_create_post(self):
        r = self.client.post('/tickets/new/', {'title': 'Testbug', 'description': 'Kaputt', 'ticket_type': 'bug', 'priority': 'high'})
        self.assertEqual(r.status_code, 302)
        from tickets.models import Ticket
        self.assertEqual(Ticket.objects.count(), 1)
        t = Ticket.objects.first()
        self.assertEqual(t.title, 'Testbug')
        self.assertEqual(t.ticket_type, 'bug')
