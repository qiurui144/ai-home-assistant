import gettext

from ai_ha.web.i18n.loader import SUPPORTED_LOCALES, get_translation, locale_from_request


def _stub_request(query: dict[str, str] | None = None,
                  cookies: dict[str, str] | None = None,
                  accept_lang: str | None = None):
    """A minimal duck-typed Request for unit tests."""
    class R:
        def __init__(self) -> None:
            self.query_params = query or {}
            self.cookies = cookies or {}
            self.headers = {"accept-language": accept_lang} if accept_lang else {}
    return R()


def test_locale_default_en():
    r = _stub_request()
    assert locale_from_request(r) == "en"


def test_locale_query_wins():
    r = _stub_request(query={"lang": "zh"}, cookies={"ai-ha-lang": "en"})
    assert locale_from_request(r) == "zh_CN"


def test_locale_cookie_used():
    r = _stub_request(cookies={"ai-ha-lang": "zh"})
    assert locale_from_request(r) == "zh_CN"


def test_locale_accept_language():
    r = _stub_request(accept_lang="zh-CN,zh;q=0.9,en;q=0.5")
    assert locale_from_request(r) == "zh_CN"


def test_locale_unknown_falls_back_to_en():
    r = _stub_request(query={"lang": "fr"})
    assert locale_from_request(r) == "en"


def test_supported_locales_includes_en_and_zh():
    assert "en" in SUPPORTED_LOCALES
    assert "zh_CN" in SUPPORTED_LOCALES


def test_get_translation_returns_translation():
    t = get_translation("en")
    assert isinstance(t, gettext.NullTranslations)  # NullTranslations or GNUTranslations
