from matcher.scam import check


def scam(**kw):
    return check(kw)[0]


def test_fee_on_private_site_is_scam():
    assert scam(title="Reporter wanted", eligibility="Pay registration fee of Rs 500 to apply", link="https://jobs-xyz.com/a")


def test_fee_on_official_site_is_only_a_note():
    is_scam, reasons, notes = check({"title": "Assistant Professor", "eligibility": "Application fee Rs. 500 for General",
                                     "official_link": "https://tripurauniv.ac.in/x.pdf"})
    assert not is_scam and notes


def test_training_payment():
    assert scam(title="Video editor", eligibility="Selected candidates must pay for training", link="https://x.com")


def test_whatsapp_only():
    assert scam(title="News anchor", how_to_apply="Apply only via WhatsApp 98xxxxxx", link="https://x.com")


def test_whatsapp_plus_email_is_fine():
    assert not scam(title="Copy editor", how_to_apply="Send CV to jobs@nenow.in or WhatsApp", link="https://nenow.in/x")


def test_bank_details_before_interview():
    assert scam(title="Content writer", eligibility="Send bank account details and Aadhaar before the interview", link="https://x.com")


def test_too_good_to_be_true():
    assert scam(title="Data entry", eligibility="Earn Rs 5000 per day, no interview", link="https://x.com")


def test_normal_notice_is_clean():
    assert not scam(title="Guest Faculty JMC", eligibility="Master's with 55% and NET", official_link="https://tripurauniv.ac.in/a")
