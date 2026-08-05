"""Email + PDF delivery.

The behaviour — validation, the 503/400/404/502 envelopes, the provider adapter, and every
branch of the client-side print path — is driven with stubs by `scripts/test_email_js.mjs`
(a fake sender, a fake store, a DOM stub); this drives that and surfaces failures here so
there is one command for the whole suite, exactly as tests/test_storage.py does.

What Python adds on top are the *structural* guards — the properties that a passing unit
test would not notice going away:

  * the endpoint is off unless someone configures it,
  * nothing sends itself,
  * the plan is never taken from the caller,
  * the provider lives in exactly one file,
  * and none of this added a dependency to a repo whose whole premise is not having any.
"""

import json
import pathlib
import re
import shutil
import subprocess
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
NODE = shutil.which("node")

EMAIL_LIB = (ROOT / "api" / "_lib" / "email-lib.js").read_text()
EMAIL_FN = (ROOT / "api" / "email.js").read_text()
DELIVERY = (ROOT / "public" / "js" / "plan-delivery.js").read_text()
DOC = (ROOT / "docs" / "EMAIL-PDF.md").read_text()


@unittest.skipUnless(NODE, "node not installed — email/PDF behaviour checks skipped")
class TestBehaviour(unittest.TestCase):
    def test_email_and_pdf_paths(self):
        proc = subprocess.run([NODE, "scripts/test_email_js.mjs"],
                              capture_output=True, text=True, cwd=ROOT)
        if proc.returncode != 0:
            self.fail("email/PDF checks failed:\n" + proc.stdout + proc.stderr)
        self.assertIn("all email + PDF checks passed", proc.stdout)


class TestDisabledByDefault(unittest.TestCase):
    """A deployment that has not opted in must do nothing, loudly and cleanly."""

    def test_missing_configuration_is_a_503_not_a_crash(self):
        self.assertIn("email_disabled", EMAIL_LIB)
        self.assertIn("503", EMAIL_LIB)

    def test_both_halves_are_required_before_sending(self):
        # A key with no verified From address is a guaranteed provider rejection — that is a
        # configuration error, not something to discover mid-send.
        m = re.search(r"export function emailEnabled\([^)]*\)\s*\{(.+?)\}", EMAIL_LIB, re.S)
        self.assertIsNotNone(m, "emailEnabled is gone — the disabled-by-default gate with it")
        self.assertIn("RESEND_API_KEY", m.group(1))
        self.assertIn("EMAIL_FROM", m.group(1))

    def test_no_api_key_is_ever_defaulted(self):
        # A hardcoded fallback key or a default From address would silently enable a feature
        # that is supposed to require a decision.
        for suspicious in ("re_", "onboarding@resend.dev", "||'", '|| "'):
            self.assertNotIn(suspicious, EMAIL_LIB,
                             f"{suspicious!r} looks like a defaulted credential")

    def test_configuration_is_read_at_call_time_not_import_time(self):
        # Importing the module must never require configuration (the lazy pattern store.js
        # uses for DATABASE_URL), or a cold start on an unconfigured deploy throws.
        top = EMAIL_LIB.split("export function createEmailHandler")[0]
        module_level = [ln for ln in top.splitlines()
                        if ln.startswith("const ") and "process.env" in ln]
        self.assertEqual(
            [ln for ln in module_level if "RESEND_API_KEY" in ln or "EMAIL_FROM" in ln], [],
            "credentials are read at import time; read them inside the call instead",
        )


class TestNothingSendsItself(unittest.TestCase):
    """The hard rule: a draft is prepared, a human sends it."""

    def test_the_pipeline_never_calls_the_email_seam(self):
        # If the planner could mail on completion, one submitted form would become outbound
        # mail with nobody's finger on the trigger. Nothing on the server may reach the seam.
        # Matched on real references (an import, the module, the route, the factory) rather
        # than the word "email", so prose in a comment cannot trip this.
        forbidden = ("email-lib", "createEmailHandler", "createResendSender",
                     "/api/email", "sendViaResend")
        for name in ("plan.js", "_lib/handler.js", "_lib/sdk-runner.js", "_lib/store.js"):
            src = (ROOT / "api" / name).read_text()
            for ref in forbidden:
                self.assertNotIn(ref, src,
                                 f"api/{name} reaches the email seam — the pipeline must not send")

    def test_there_is_no_recipient_list_anywhere(self):
        for word in ("subscribers", "mailing_list", "mailingList", "recipients"):
            self.assertNotIn(word, EMAIL_LIB, "this endpoint mails one typed address, never a list")

    def test_exactly_one_recipient_reaches_the_provider(self):
        self.assertIn("to: [message.to]", EMAIL_LIB)

    def test_a_second_recipient_cannot_be_smuggled_in(self):
        # Enforced by the address pattern rejecting , ; < > and whitespace. The behavioural
        # proof is in the Node suite; this guards the pattern itself from being loosened.
        m = re.search(r"const EMAIL_RE = /(.+)/;", EMAIL_LIB)
        self.assertIsNotNone(m, "the address pattern is gone")
        for forbidden in (",", ";", "<", ">", r"\s"):
            self.assertIn(forbidden, m.group(1),
                          f"the address pattern no longer excludes {forbidden!r}")


class TestThePlanComesFromTheStore(unittest.TestCase):
    """The open-relay guard: content is looked up, never accepted."""

    def test_the_allowed_fields_are_only_the_three(self):
        m = re.search(r"ALLOWED_EMAIL_FIELDS = Object\.freeze\(\[(.*?)\]\)", EMAIL_LIB, re.S)
        self.assertIsNotNone(m)
        fields = set(re.findall(r"'([^']+)'", m.group(1)))
        self.assertEqual(fields, {"to", "run_id", "note"})

    def test_the_handler_reads_the_plan_through_the_store_seam(self):
        self.assertIn("store.getRun(clean.run_id)", EMAIL_LIB)

    def test_no_html_is_ever_taken_from_the_request_body(self):
        self.assertNotIn("req.body.plan_html", EMAIL_LIB)
        self.assertNotIn("body.plan_html", EMAIL_LIB)
        # The client-side body builder must not carry it either.
        m = re.search(r"export function emailRequestBody.+?\n\}", DELIVERY, re.S)
        self.assertIsNotNone(m)
        self.assertNotIn("plan_html:", m.group(0))
        self.assertNotIn("planHtml", m.group(0))

    def test_the_emailed_link_is_not_built_from_request_headers(self):
        # A Host header is caller-controlled; a link in outbound mail must not be.
        self.assertNotIn("req.headers.host", EMAIL_LIB)
        self.assertNotIn("headers['host']", EMAIL_LIB)
        self.assertIn("PUBLIC_ORIGIN", EMAIL_LIB)


class TestProviderIsolation(unittest.TestCase):
    """One file knows what a provider is — the seam the tests inject around."""

    def test_the_provider_is_named_in_exactly_one_file(self):
        hits = [p for p in ROOT.rglob("*.js")
                if "node_modules" not in p.parts and "api.resend.com" in p.read_text()]
        self.assertEqual([p.name for p in hits], ["email-lib.js"],
                         "provider code escaped the seam")

    def test_the_route_file_is_wiring_only(self):
        # Same shape as api/plan.js and api/plan/[id].js: import the seam, export it wired.
        self.assertIn("createEmailHandler", EMAIL_FN)
        self.assertIn("export default", EMAIL_FN)
        self.assertNotIn("resend.com", EMAIL_FN)
        code = [ln for ln in EMAIL_FN.splitlines()
                if ln.strip() and not ln.strip().startswith("//")]
        self.assertLessEqual(len(code), 5, "logic is leaking into the route file")

    def test_the_handler_takes_its_sender_by_injection(self):
        self.assertIn("createEmailHandler({ send, store", EMAIL_LIB)

    def test_no_sdk_was_added_for_any_of_this(self):
        deps = json.loads((ROOT / "package.json").read_text()).get("dependencies", {})
        for banned in ("resend", "nodemailer", "@sendgrid/mail", "postmark",
                       "puppeteer", "puppeteer-core", "playwright", "jspdf",
                       "html2pdf.js", "html2canvas", "pdfkit", "@react-pdf/renderer"):
            self.assertNotIn(banned, deps,
                             f"{banned} was added — this repo has no bundler and a strict CSP")


class TestClientSideIsCspSafe(unittest.TestCase):
    """No bundler, no CDN — the constraint that dictated the whole PDF approach."""

    def test_the_delivery_module_loads_nothing_off_site(self):
        for bad in ("http://", "cdn.", "unpkg", "jsdelivr", "importScripts"):
            self.assertNotIn(bad, DELIVERY, f"plan-delivery.js reaches for {bad!r}")
        # The one https:// reference allowed anywhere near this is in the docs, not the module.
        self.assertNotIn("https://", DELIVERY)

    def test_the_pdf_path_is_the_browser_s_own_print(self):
        self.assertIn("srcdoc", DELIVERY)
        self.assertIn(".print()", DELIVERY)

    def test_the_print_frame_never_gets_allow_scripts(self):
        # allow-same-origin is required to reach contentWindow.print(); combined with
        # allow-scripts it would let model-generated HTML unsandbox itself.
        m = re.search(r"setAttribute\('sandbox', '([^']*)'\)", DELIVERY)
        self.assertIsNotNone(m, "the print frame is no longer sandboxed at all")
        self.assertNotIn("allow-scripts", m.group(1))
        self.assertIn("allow-same-origin", m.group(1))

    def test_every_failure_branch_rejects_rather_than_hanging(self):
        for code in ("empty_plan", "no_document", "load_timeout",
                     "no_frame_window", "print_blocked"):
            self.assertIn(code, DELIVERY)

    def test_the_frame_is_always_cleaned_up(self):
        self.assertIn("remove()", DELIVERY)
        self.assertIn("PDF_CLEANUP_DELAY_MS", DELIVERY)


class TestDocumentation(unittest.TestCase):
    """The doc is the deliverable for anyone switching this on."""

    def test_it_names_the_environment_variables(self):
        for var in ("RESEND_API_KEY", "EMAIL_FROM", "PUBLIC_ORIGIN"):
            self.assertIn(var, DOC)

    def test_it_covers_domain_verification(self):
        self.assertIn("verif", DOC.lower())

    def test_it_is_honest_about_the_attachment_being_html(self):
        low = DOC.lower()
        self.assertIn("headless", low, "the HTML-not-PDF tradeoff must be explained")
        self.assertTrue("html, not a pdf" in low or "html, not pdf" in low
                        or "not a pdf" in low)

    def test_it_carries_the_wiring_snippet_unapplied(self):
        # The snippet is for a human to paste into public/index.html — a file this work
        # deliberately does not touch. It must be present, and it must be fenced.
        self.assertIn("```html", DOC)
        self.assertIn("plan-delivery.js", DOC)
        self.assertIn("/api/email", DOC)

    def test_the_snippet_imports_what_the_module_actually_exports(self):
        snippet = "\n".join(
            block for block in re.findall(r"```(?:html|js)\n(.*?)```", DOC, re.S)
        )
        self.assertTrue(snippet.strip(), "no fenced snippet found in the doc")
        for name in re.findall(r"import \{([^}]+)\} from '\./js/plan-delivery\.js'", snippet):
            for symbol in (s.strip() for s in name.split(",")):
                self.assertIn(f"export function {symbol}", DELIVERY,
                              f"the snippet imports {symbol}, which the module does not export")

    def test_it_states_what_was_deliberately_not_wired(self):
        low = DOC.lower()
        self.assertIn("not wired", low)


if __name__ == "__main__":
    unittest.main()
