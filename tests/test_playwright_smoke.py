from playwright.sync_api import sync_playwright


def test_playwright_can_render_pdf(tmp_path):
    output = tmp_path / "smoke.pdf"
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.set_content("<html><body><h1>Teste</h1></body></html>")
        page.pdf(path=str(output), format="A4")
        browser.close()
    assert output.exists()
    assert output.stat().st_size > 1000
