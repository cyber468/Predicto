import hmac
import logging
from functools import wraps

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.hashers import check_password, make_password
from django.core.exceptions import ValidationError
from django.core.mail import send_mail
from django.db import IntegrityError
import re
from django.core.validators import validate_email
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from . import ml
from .models import clusterNum, registration_details, user_answers
from .questions import QUESTIONS, TRAITS

logger = logging.getLogger(__name__)

SCALE = [("1", "Strongly disagree"), ("2", "Disagree"), ("3", "Neutral"), ("4", "Agree"), ("5", "Strongly agree")]
HASH_PREFIX = "pbkdf2_"  # Django's default hasher; anything else is a legacy plaintext password


def _current_user(request):
    username = request.session.get("username")
    return registration_details.objects.filter(pk=username).first() if username else None


def login_required(view):
    @wraps(view)
    def wrapper(request, *args, **kwargs):
        user = _current_user(request)
        if user is None:
            request.session.flush()
            messages.error(request, "Log in to continue.")
            return redirect("login")
        request.user_row = user
        return view(request, *args, **kwargs)

    return wrapper


def _password_ok(user, password):
    stored = user.password or ""
    if not stored or not password:
        return False  # legacy rows with no password must never match an empty one
    if stored.startswith(HASH_PREFIX):
        return check_password(password, stored)
    # Legacy account created before passwords were hashed: compare, then upgrade.
    if hmac.compare_digest(stored.encode(), password.encode()):
        user.password = make_password(password)
        user.save(update_fields=["password"])
        return True
    return False


def login(request):
    if request.method == "POST":
        username = request.POST.get("username", "").strip()
        password = request.POST.get("password", "")
        user = registration_details.objects.filter(pk=username).first()
        if user is None:
            make_password(password)  # spend the same time as a real check so timing does not reveal usernames
        if user and _password_ok(user, password):
            request.session.flush()  # new session id, nothing carried over from before login
            request.session["username"] = user.username
            has_result = clusterNum.objects.filter(pk=user.username).exists()
            return redirect("result" if has_result else "question")
        messages.error(request, "That username and password don't match.")
        return render(request, "login.html", {"username": username}, status=200)
    if _current_user(request):
        return redirect("result")
    return render(request, "login.html")


def register(request):
    if request.method != "POST":
        return render(request, "register.html")

    data = {k: request.POST.get(k, "").strip() for k in ("fullname", "username", "mobileno", "email")}
    password = request.POST.get("password", "")
    errors = {}
    if not data["fullname"] or len(data["fullname"]) > 30:
        errors["fullname"] = "Enter your name (30 characters or fewer)."
    if not 3 <= len(data["username"]) <= 30 or " " in data["username"]:
        errors["username"] = "Use 3 to 30 characters with no spaces."
    elif registration_details.objects.filter(pk=data["username"]).exists():
        errors["username"] = "That username is taken. Try another."
    if len(password) < 8:
        errors["password"] = "Use at least 8 characters."
    try:
        validate_email(data["email"])
    except ValidationError:
        errors["email"] = "Enter a valid email address."
    if data["mobileno"] and not re.fullmatch(r"\+?\d{6,14}", data["mobileno"]):
        errors["mobileno"] = "Use 6 to 14 digits, with an optional leading +."

    if errors:
        return render(request, "register.html", {"errors": errors, "values": data}, status=200)

    try:
        registration_details.objects.create(password=make_password(password), **data)
    except IntegrityError:  # two submissions raced for the same username
        errors["username"] = "That username is taken. Try another."
        return render(request, "register.html", {"errors": errors, "values": data}, status=200)
    messages.success(request, "Account created. Log in to start the quiz.")
    return redirect("login")


@require_POST
def logout(request):
    request.session.flush()
    return redirect("login")


@login_required
def question(request):
    user = request.user_row
    if request.method == "POST":
        values = {}
        for i in range(1, len(QUESTIONS) + 1):
            raw = request.POST.get(f"qu{i}", "")
            if raw not in ("1", "2", "3", "4", "5"):
                messages.error(request, "Answer all 50 statements before you finish.")
                return redirect("question")
            values[f"q{i}"] = float(raw)  # stored raw (5 = strongly agree); keying happens in ml.py
        user_answers.objects.update_or_create(username_id=user.username, defaults=values)
        clusterNum.objects.filter(pk=user.username).delete()  # force a fresh prediction
        return redirect("result")

    retaking = clusterNum.objects.filter(pk=user.username).exists()
    return render(request, "question.html", {"questions": [q for q, _ in QUESTIONS], "retaking": retaking, "scale": SCALE})


@login_required
def result(request):
    user = request.user_row
    answers = user_answers.objects.filter(pk=user.username).first()
    values = [getattr(answers, f"q{i}", None) for i in range(1, 51)] if answers else []
    if len(values) != 50 or None in values:
        return redirect("question")

    mine = ml.trait_scores(values)
    cluster, group = ml.predict(values)
    _, created = clusterNum.objects.update_or_create(
        username_id=user.username,
        defaults=dict(zip(
            ("clusNo", "extroversion", "neurotic", "agreeable", "conscientious", "openness"),
            (cluster, *group),
        )),
    )
    if created:
        _email_results(user, group)

    traits = [
        {"key": key, "label": label, "desc": desc, "mine": mine[i], "group": group[i]}
        for i, (key, label, desc) in enumerate(TRAITS)
    ]
    def shade(v):  # 1..5 -> opacity of a dot
        return round(0.15 + (v - 1) / 4 * 0.85, 2)

    rows = []
    for t, (_, label, _) in enumerate(TRAITS):
        dots = []
        for i in range(t * 10, t * 10 + 10):
            raw = int(values[i])
            rev = bool(ml.REVERSED[i])
            keyed = 6 - raw if rev else raw
            dots.append({"text": QUESTIONS[i][0], "raw": raw, "keyed": keyed, "rev": rev,
                         "ro": shade(raw), "ko": shade(keyed), "d": round((i % 10) * 0.05 + t * 0.04, 2)})
        rows.append({"label": label, "t": t, "dots": dots, "mine": mine[t]})
    return render(request, "result.html", {
        "name": user.fullname or user.username, "traits": traits, "cluster": cluster, "rows": rows,
        "reversed_count": int(ml.REVERSED.sum()), "total": len(values),
        "statements": [q for q, _ in QUESTIONS],
    })


def _email_results(user, group):
    if not (settings.EMAIL_HOST_USER and settings.EMAIL_HOST_PASSWORD and user.email):
        return
    lines = [f"{label}: {group[i]}%" for i, (_, label, _) in enumerate(TRAITS)]
    try:
        send_mail("Your Predicto results", "Your results:\n" + "\n".join(lines),
                  settings.EMAIL_HOST_USER, [user.email], fail_silently=False)
    except Exception:
        logger.exception("Could not email results to %s", user.username)
