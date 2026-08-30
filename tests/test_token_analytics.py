from dana.tools.token_analytics import estimate_tokens
def test_estimate_tokens():
    assert estimate_tokens('')==0
    assert estimate_tokens('abcdefgh')==2
