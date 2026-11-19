from django.core import mail
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from .models import clusterNum, registration_details, user_answers
from .questions import QUESTIONS

ANSWERS = {f"qu{i}": "4" for i in range(1, 51)}
USER = {"fullname": "Vic", "username": "victim", "password": "correct-horse", "email": "v@example.com", "mobileno": ""}


def register(client, **over):
    return client.post(reverse("register"), {**USER, **over})


class AuthTests(TestCase):
    def test_password_is_hashed(self):
        register(self.client)
        self.assertTrue(registration_details.objects.get(pk="victim").password.startswith("pbkdf2_"))

    def test_failed_login_does_not_grant_access(self):  # was an auth bypass via session["username"]
        register(self.client)
        user_answers.objects.create(username_id="victim", **{f"q{i}": 3.0 for i in range(1, 51)})
        self.client.post(reverse("login"), {"username": "victim", "password": "WRONG"})
        r = self.client.get(reverse("result"))
        self.assertRedirects(r, reverse("login"))
        self.assertNotIn("password", self.client.session)

    def test_login_then_logout(self):
        register(self.client)
        r = self.client.post(reverse("login"), {"username": "victim", "password": USER["password"]})
        self.assertRedirects(r, reverse("question"))
        self.client.post(reverse("logout"))
        self.assertRedirects(self.client.get(reverse("question")), reverse("login"))

    def test_legacy_plaintext_account_is_upgraded(self):
        registration_details.objects.create(username="old", password="plain1234", fullname="Old")
        self.client.post(reverse("login"), {"username": "old", "password": "plain1234"})
        self.assertTrue(registration_details.objects.get(pk="old").password.startswith("pbkdf2_"))

    def test_register_validation(self):
        r = register(self.client, password="short")
        self.assertContains(r, "at least 8")
        register(self.client)
        self.assertContains(register(self.client), "taken")


class QuizTests(TestCase):
    def setUp(self):
        register(self.client)
        self.client.post(reverse("login"), {"username": "victim", "password": USER["password"]})

    def test_result_before_quiz_redirects(self):  # was UnboundLocalError
        self.assertRedirects(self.client.get(reverse("result")), reverse("question"))

    def test_incomplete_or_invalid_answers_rejected(self):  # was float(None) 500 / unvalidated
        bad = dict(ANSWERS); del bad["qu7"]
        self.assertRedirects(self.client.post(reverse("question"), bad), reverse("question"))
        bad = dict(ANSWERS); bad["qu7"] = "999"
        self.assertRedirects(self.client.post(reverse("question"), bad), reverse("question"))
        self.assertFalse(user_answers.objects.exists())

    def test_answers_stored_raw(self):  # the model is trained on raw agreement, so storage must be raw
        self.client.post(reverse("question"), {f"qu{i}": "5" for i in range(1, 51)})
        row = user_answers.objects.get(pk="victim")
        self.assertEqual({getattr(row, f"q{i}") for i in range(1, 51)}, {5.0})

    def test_result_refresh_does_not_crash(self):  # was IntegrityError on 2nd visit
        self.client.post(reverse("question"), ANSWERS)
        self.assertEqual(self.client.get(reverse("result")).status_code, 200)
        self.assertEqual(self.client.get(reverse("result")).status_code, 200)
        self.assertEqual(clusterNum.objects.count(), 1)

    def test_retake_replaces_result(self):  # was IntegrityError on 2nd quiz POST
        self.client.post(reverse("question"), ANSWERS)
        self.client.get(reverse("result"))
        r = self.client.post(reverse("question"), {f"qu{i}": "1" for i in range(1, 51)})
        self.assertRedirects(r, reverse("result"))
        self.assertEqual(self.client.get(reverse("result")).status_code, 200)
        self.assertEqual(user_answers.objects.count(), 1)

    def test_scores_are_percentages(self):
        self.client.post(reverse("question"), ANSWERS)
        for t in self.client.get(reverse("result")).context["traits"]:
            self.assertTrue(0 <= t["mine"] <= 100 and 0 <= t["group"] <= 100)


class HardeningTests(TestCase):
    def login(self):
        register(self.client)
        self.client.post(reverse("login"), {"username": "victim", "password": USER["password"]})

    def test_legacy_account_without_password_cannot_log_in_empty(self):
        registration_details.objects.create(username="ghost", password=None, fullname="G")
        registration_details.objects.create(username="blank", password="", fullname="B")
        for name in ("ghost", "blank"):
            self.client.post(reverse("login"), {"username": name, "password": ""})
            self.assertNotIn("username", self.client.session)
        self.assertIsNone(registration_details.objects.get(pk="ghost").password)

    def test_second_login_works_after_legacy_upgrade(self):
        registration_details.objects.create(username="old", password="plain1234", fullname="Old")
        for _ in range(2):
            self.client.post(reverse("logout"))
            self.client.post(reverse("login"), {"username": "old", "password": "plain1234"})
            self.assertEqual(self.client.session.get("username"), "old")

    def test_logout_requires_post(self):
        self.login()
        self.assertEqual(self.client.get(reverse("logout")).status_code, 405)

    def test_csrf_enforced_on_login(self):
        c = Client(enforce_csrf_checks=True)
        self.assertEqual(c.post(reverse("login"), {"username": "x", "password": "y"}).status_code, 403)

    def test_known_answers_give_known_scores(self):
        self.login()
        self.client.post(reverse("question"), {f"qu{i}": "5" for i in range(1, 51)})
        mine = {t["key"]: t["mine"] for t in self.client.get(reverse("result")).context["traits"]}
        # "Strongly agree" everywhere scores (positive*5 + negative*1) / 50. The official IPIP-50 key has
        # positive/negative item counts of 5/5, 2/8, 6/4, 6/4 and 7/3 for the five traits.
        self.assertEqual(mine, {"extroversion": 60.0, "neurotic": 36.0, "agreeable": 68.0,
                                "conscientious": 68.0, "openness": 76.0})

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
                       EMAIL_HOST_USER="app@example.com", EMAIL_HOST_PASSWORD="x")
    def test_email_sent_once(self):
        self.login()
        self.client.post(reverse("question"), ANSWERS)
        self.client.get(reverse("result")); self.client.get(reverse("result"))
        self.assertEqual(len(mail.outbox), 1)

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.smtp.EmailBackend", EMAIL_HOST="127.0.0.1",
                       EMAIL_PORT=1, EMAIL_HOST_USER="app@example.com", EMAIL_HOST_PASSWORD="x")
    def test_smtp_failure_still_shows_result(self):
        self.login()
        self.client.post(reverse("question"), ANSWERS)
        self.assertEqual(self.client.get(reverse("result")).status_code, 200)

    def test_mobile_number_validation(self):
        self.assertContains(register(self.client, mobileno="+++"), "6 to 14 digits")


class ScoringTests(TestCase):
    """Guards the science: item keys, raw model input, and the group profile."""

    # Negatively keyed items per the IPIP 50-item key (https://ipip.ori.org/New_IPIP-50-item-scale.htm).
    NEGATIVE = {
        "I don't talk a lot.", "I keep in the background.", "I have little to say.",
        "I don't like to draw attention to myself.", "I am quiet around strangers.",
        "I feel very little concern for others.", "I insult people.", "I am not interested in others problems.",
        "I am not really interested in others.",
        "I get stressed out easily.", "I worry about things.", "I am easily disturbed.", "I get upset easily.",
        "I change my mood a lot.", "I have frequent mood swings.", "I get irritated easily.", "I often feel blue.",
        "I leave my belongings around.", "I make a mess of things.", "I often forget to put things back in their place.",
        "I shirk(neglect) my duties.",
        "I have difficulty in understanding abstract ideas.", "I am not interested in abstracts.",
        "I do not have a good imagination.",
    }

    def test_reverse_flags_match_official_key(self):
        flagged = {text for text, rev in QUESTIONS if rev}
        self.assertEqual(flagged, self.NEGATIVE)
        self.assertEqual(len(flagged), 24)

    def test_model_receives_raw_answers(self):
        from unittest import mock
        from . import ml
        raw = [float(1 + i % 5) for i in range(50)]
        real = ml.get_model()
        with mock.patch.object(ml, "get_model") as gm:
            gm.return_value.predict.return_value = [2]
            gm.return_value.cluster_centers_ = real.cluster_centers_
            ml.predict(raw)
        self.assertEqual(gm.return_value.predict.call_args[0][0], [raw])

    def test_group_profile_applies_the_key_to_centroids(self):
        from . import ml
        model = ml.get_model()
        for k in range(5):
            naive = [round(float(x), 2) for x in model.cluster_centers_[k].reshape(5, 10).mean(axis=1) / 5 * 100]
            self.assertNotEqual(ml.trait_scores(model.cluster_centers_[k]), naive)

    def test_a_centroid_respondent_lands_in_their_own_cluster(self):
        import numpy as np
        from . import ml
        model = ml.get_model()
        for k in range(5):
            self.assertEqual(ml.predict(np.clip(np.rint(model.cluster_centers_[k]), 1, 5))[0], k)
