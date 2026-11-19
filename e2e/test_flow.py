"""Browser test. Needs the dev server running: python manage.py runserver 127.0.0.1:8765
Run: .venv/bin/python e2e/test_flow.py"""
import pathlib
import sys
import time
from playwright.sync_api import sync_playwright, expect

BASE = "http://127.0.0.1:8765"
SHOTS = pathlib.Path(__file__).parent / "shots"
user = f"e2e{int(time.time())}"
errors = []


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch()
        ctx = browser.new_context(viewport={"width": 1280, "height": 800})
        page = ctx.new_page()
        page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
        page.on("pageerror", lambda e: errors.append(str(e)))

        page.goto(BASE)
        page.screenshot(path=SHOTS / "1-login.png")

        # anon access is redirected
        page.goto(BASE + "/personality/result")
        expect(page).to_have_url(BASE + "/")
        expect(page.locator(".flash")).to_contain_text("Log in to continue")

        # register validation
        page.goto(BASE + "/personality/register")
        page.fill("[name=fullname]", "Test Person")
        page.fill("[name=username]", user)
        page.fill("[name=password]", "short")
        page.fill("[name=email]", "t@example.com")
        page.click("button[type=submit]")
        expect(page.locator(".err")).to_contain_text("at least 8")
        page.screenshot(path=SHOTS / "2-register-error.png")
        page.fill("[name=password]", "longenough1")
        page.click("button[type=submit]")
        expect(page.locator(".flash")).to_contain_text("Account created")

        # wrong password
        page.fill("[name=username]", user)
        page.fill("[name=password]", "nope-nope")
        page.click("button[type=submit]")
        expect(page.locator(".flash")).to_contain_text("don't match")
        page.goto(BASE + "/personality/result")  # old auth bypass
        expect(page).to_have_url(BASE + "/")

        # login
        page.fill("[name=username]", user)
        page.fill("[name=password]", "longenough1")
        page.click("button[type=submit]")
        expect(page).to_have_url(BASE + "/personality/question")

        # quiz with keyboard: 50 answers, last one reveals the finish button
        expect(page.locator("#cur")).to_have_text("1")
        page.keyboard.press("4")
        expect(page.locator("#cur")).to_have_text("2")
        page.click("#back")
        expect(page.locator("#cur")).to_have_text("1")
        page.screenshot(path=SHOTS / "3-quiz.png")

        # regression: two quick presses must not skip a question or leave one unanswered
        page.keyboard.press("5"); page.keyboard.press("5")
        page.wait_for_timeout(500)
        expect(page.locator("#cur")).to_have_text("2")
        page.click("#back")
        expect(page.locator("#cur")).to_have_text("1")
        # regression: arrow keys select but do not auto-advance; focus lands on the visible question
        page.keyboard.press("ArrowLeft"); page.keyboard.press("ArrowRight")
        page.wait_for_timeout(400)
        expect(page.locator("#cur")).to_have_text("1")
        assert page.evaluate("document.activeElement.closest('.item').classList.contains('on')")
        expect(page.locator("#next")).to_be_visible()
        page.click("#next")
        expect(page.locator("#cur")).to_have_text("2")
        page.click("#back")
        for i in range(50):
            page.keyboard.press(str(1 + i % 5))
            if i < 49:
                expect(page.locator("#cur")).to_have_text(str(i + 2))
        expect(page.locator("#finish")).to_be_visible()
        page.screenshot(path=SHOTS / "4-quiz-end.png")
        page.click("#finish")

        # result, then refresh twice (used to crash)
        expect(page).to_have_url(BASE + "/personality/result")
        expect(page.locator("#radar polygon.group")).to_have_count(1)
        expect(page.locator(".trait")).to_have_count(5)
        page.screenshot(path=SHOTS / "5-result.png", full_page=True)
        # science content: 4 research cards, 5 references with 3 DOI links, 50 dots (24 reverse-scored), keyed labels
        expect(page.locator(".card")).to_have_count(4)
        expect(page.locator(".refs li")).to_have_count(5)
        expect(page.locator(".refs a[href^='https://doi.org/']")).to_have_count(3)
        expect(page.locator(".dots .d")).to_have_count(50)
        expect(page.locator(".dots .d.rev")).to_have_count(24)
        expect(page.locator(".trait h2").nth(1)).to_have_text("Emotional stability")
        expect(page.locator(".limits")).to_contain_text("not a rank")
        # animation reaches its final state: counters land on the real values, dots reach stage 3
        page.wait_for_timeout(500)
        page.evaluate("document.getElementById('dots').scrollIntoView({block:'center'})")
        page.wait_for_function("document.getElementById('dots').classList.contains('p3')", timeout=15000)
        page.wait_for_timeout(2500)
        shown = page.locator(".dnum").all_inner_texts()
        truth = [r.get_attribute("data-to") for r in page.locator(".dnum").all()]
        assert [float(x.rstrip('%')) for x in shown] == [float(t) for t in truth], (shown, truth)
        page.reload(); page.reload()
        expect(page.locator(".trait")).to_have_count(5)

        # mobile
        m = browser.new_context(viewport={"width": 390, "height": 800}, storage_state=ctx.storage_state()).new_page()
        m.goto(BASE + "/personality/result")
        assert m.evaluate("document.documentElement.scrollWidth <= window.innerWidth"), "horizontal scroll on mobile"
        m.screenshot(path=SHOTS / "6-result-mobile.png", full_page=True)

        # retake
        page.click("text=Retake the quiz")
        expect(page).to_have_url(BASE + "/personality/question")
        expect(page.locator(".count")).to_contain_text("retaking")

        # no-JS fallback: all questions render and the submit button is available
        nojs = browser.new_context(java_script_enabled=False, storage_state=ctx.storage_state()).new_page()
        nojs.goto(BASE + "/personality/question")
        expect(nojs.locator(".item")).to_have_count(50)
        expect(nojs.locator("#finish")).to_be_visible()
        expect(nojs.locator("#back")).to_be_hidden()

        # reduced motion: finished page, no armed animation state
        rm = browser.new_context(reduced_motion="reduce", storage_state=ctx.storage_state()).new_page()
        rm.goto(BASE + "/personality/result")
        assert not rm.evaluate("document.getElementById('dots').classList.contains('armed')")
        assert not rm.evaluate("document.querySelector('.cards').classList.contains('reveal')")
        expect(rm.locator(".dnum").first).not_to_have_text("0%")

        # logout
        page.click("text=Log out")
        expect(page).to_have_url(BASE + "/")
        page.goto(BASE + "/personality/question")
        expect(page).to_have_url(BASE + "/")
        browser.close()
    real = [e for e in errors if "fonts.g" not in e and "ERR_" not in e]
    if real:
        print("CONSOLE ERRORS:", real); sys.exit(1)
    print("E2E PASS")


main()
