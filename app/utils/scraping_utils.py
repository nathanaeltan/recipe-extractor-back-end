from bs4 import BeautifulSoup

def preprocess_html(html_content: str) -> str:
    """Remove scripts, styles, and non-content elements from HTML and return text."""
    soup = BeautifulSoup(html_content, 'html.parser')
    for tag in soup(["script", "style", "header", "footer", "nav", "aside"]):
        tag.extract()
    return soup.get_text(separator="\n")
