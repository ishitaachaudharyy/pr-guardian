from app.reviewer import build_diff, format_comment

def test_build_diff_skips_missing_patch():
    result = build_diff([
        {"filename": "a.py", "patch": "@@ -1 +1 @@\n-old\n+new"},
        {"filename": "image.png"}
    ])
    assert "a.py" in result
    assert "image.png" not in result

def test_comment_warns_about_ai():
    body = format_comment("Example", [], "Review done")
    assert "not a guarantee" in body
    assert "can be incorrect" in body
