from io import StringIO
from markdown import Markdown


def strip_markdown_text(markdown_text: str) -> str:
    def unmark_element(element, stream=None):
        if stream is None:
            stream = StringIO()
        if element.text:
            stream.write(element.text)
        for sub in element:
            unmark_element(sub, stream)
        if element.tail:
            stream.write(element.tail)
        return stream.getvalue()

    Markdown.output_formats["plain"] = unmark_element
    markdown = Markdown(output_format="plain")
    markdown.stripTopLevelTags = False
    return markdown.convert(markdown_text)
