import httpx
from types import SimpleNamespace

from backend.services import research_service


def _install_mock_transport(monkeypatch, handler):
    original_client = httpx.Client
    transport = httpx.MockTransport(handler)
    monkeypatch.setattr(
        research_service.httpx,
        "Client",
        lambda **kwargs: original_client(transport=transport, **kwargs),
    )


def test_website_research_fetches_relevant_pages_and_cites_sources(monkeypatch):
    requests = []
    pages = {
        "/": """<html><head><title>Northstar &amp; Co</title>
            <meta content='Automation for modern warehouses' name='description'></head>
            <body><nav>Navigation noise</nav><h1>Warehouse automation</h1>
            <p>Northstar builds inventory planning tools.</p>
            <a href='/about'>About our company</a><a href='/products'>Platform</a>
            <a href='https://outside.example/about'>External page</a>
            <script>Do not include secret script text.</script></body></html>""",
        "/about": "<html><body><h2>Our company</h2><p>Founded to reduce stockouts.</p></body></html>",
        "/products": "<html><body><h1>Inventory platform</h1><p>Demand planning software.</p></body></html>",
    }

    def handler(request):
        requests.append(request)
        return httpx.Response(
            200,
            headers={"content-type": "text/html; charset=utf-8"},
            text=pages[request.url.path],
        )

    _install_mock_transport(monkeypatch, handler)

    research = research_service.build_research(SimpleNamespace(
        website="https://example.com",
        linkedin=None,
    ))

    summary = research["website_summary"]
    assert "Northstar & Co" in summary
    assert "Automation for modern warehouses" in summary
    assert research["website_sources"] == [
        "https://example.com/", "https://example.com/about", "https://example.com/products"
    ]
    assert "Navigation noise" not in summary
    assert "secret script text" not in summary
    assert all(request.url.host == "example.com" for request in requests)
    assert len(requests) == 3


def test_website_research_rejects_redirect_to_private_address(monkeypatch):
    requests = []

    def handler(request):
        requests.append(request)
        return httpx.Response(302, headers={"location": "http://127.0.0.1/admin"})

    _install_mock_transport(monkeypatch, handler)

    assert research_service.fetch_website_summary("https://example.com") is None
    assert len(requests) == 1
    assert requests[0].url.host == "example.com"


def test_website_research_skips_private_literal_addresses():
    assert research_service.fetch_website_summary("http://127.0.0.1") is None
    assert research_service.fetch_website_summary("http://localhost") is None