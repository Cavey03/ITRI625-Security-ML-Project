import pandas as pd

from src.data import deduplicate, near_key, split
from src.preprocess import clean_email, clean_field


def test_html_stripped_and_entities_decoded():
    assert clean_field("<html><body><p>Click&nbsp;<b>here</b></p><script>x=1</script></body></html>") == "Click here"


def test_urls_kept():
    assert "http://evil.example.com/login" in clean_field("go to http://evil.example.com/login now")


def test_emails_and_years_masked():
    out = clean_field("Contact bob@corp.example.com before 2019. Tokenised: liz . bellamy @ enron . com")
    assert "bob@" not in out and "bellamy" not in out and "2019" not in out
    assert out.count("[email]") == 2 and "[year]" in out


def test_short_header_lines_removed_but_long_lines_kept():
    body = "Message-ID: <abc@x.example.com>\nX-Mailer: Foo 1.0\nHello there"
    assert clean_field(body) == "Hello there"
    glued = "Date: Wed, 21 Aug 2002 " + "real body text " * 30   # header glued to a long line
    assert "real body text" in clean_field(glued)


def test_tokenised_separator_squashed():
    assert clean_field("a - - - - - - b ________ c") == "a --- b ___ c"


def test_mime_encoded_words_decoded():
    assert clean_field("=?utf-8?B?WW91ciBOZXRmbGl4IE1lbWJlcnNoaXAgaXMgb24gaG9sZA==?=") == "Your Netflix Membership is on hold"
    assert clean_field("= ? utf - 8 ? q ? up - to - date course ? =") == "up - to - date course"


def test_address_lists_collapse_and_recipient_masked():
    assert clean_field("to: a@x.example.com, b@y.example.com, c@z.example.com\nhi") == "hi"   # header line
    assert clean_field("cc a@x.example.com, b@y.example.com; c@z.example.com end") == "cc [email] end"
    assert clean_field("Dear jose, log in at monkey.org now") == "Dear , log in at now"


def test_clean_email_builds_text():
    s, b, t = clean_email("Hi", "Body")
    assert (s, b, t) == ("Hi", "Body", "Hi\n\nBody")
    assert clean_email(None, "Body")[2] == "Body"


def test_near_key_ignores_case_numbers_urls_spacing():
    assert near_key("Pay $100 at http://a.example.com/x1 , now") == near_key("pay $250 at https://b.example.org/y2, NOW")


def test_dedup_keeps_one_copy_and_drops_label_conflicts():
    df = pd.DataFrame({"text": ["same", "same", "SAME!", "clash", "clash", "unique"],
                       "label": [1, 1, 1, 0, 1, 0]})
    out, rep = deduplicate(df)
    assert sorted(out["text"]) == ["same", "unique"]
    assert rep["exact_duplicates_removed"] == 1 and rep["exact_label_conflicts_removed"] == 2
    assert rep["near_duplicates_removed"] == 1


def test_split_is_disjoint_stratified_and_deterministic():
    df = pd.DataFrame({"text": [f"t{i}" for i in range(400)], "id": [f"{i}" for i in range(400)],
                       "label": [i % 2 for i in range(400)], "source": ["A", "B"] * 100 + ["C"] * 200})
    a, b = split(df), split(df)
    assert all(a[k].index.equals(b[k].index) for k in a)
    ids = [set(a[k]["id"]) for k in ("train", "val", "test")]
    assert not (ids[0] & ids[1] or ids[0] & ids[2] or ids[1] & ids[2])
    assert sum(map(len, ids)) == 400
    assert [len(a[k]) for k in ("train", "val", "test")] == [280, 60, 60]
