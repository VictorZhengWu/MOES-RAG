"""Research PDF export (00108-03).

WHAT: Converts Deep Research Markdown reports to PDF via markdown + weasyprint.
      Falls back to plain text if weasyprint is not installed.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


async def export_report_pdf(report_md: str) -> bytes:
    """Convert a Markdown research report to PDF bytes.

    Args:
        report_md: The full Markdown report string.

    Returns:
        PDF bytes, or plain text bytes if weasyprint not available.
    """
    try:
        import markdown
        html = markdown.markdown(report_md, extensions=['tables', 'fenced_code'])
        styled = f"""<!DOCTYPE html><html><head><meta charset="utf-8">
<style>body{{font-family:Arial,sans-serif;max-width:800px;margin:40px auto;line-height:1.6}}
h1{{font-size:20px}}h2{{font-size:16px;margin-top:24px}}h3{{font-size:14px}}
table{{border-collapse:collapse;width:100%}}td,th{{border:1px solid #ddd;padding:6px;font-size:12px}}
strong{{color:#1a1a1a}}p{{font-size:13px}}</style></head>
<body>{html}</body></html>"""

        try:
            import weasyprint
            return weasyprint.HTML(string=styled).write_pdf()
        except ImportError:
            # Fallback: return HTML wrapped as text
            logger.info("weasyprint not installed, returning HTML text")
            return styled.encode('utf-8')

    except ImportError:
        logger.info("markdown not installed, returning raw text")
        return report_md.encode('utf-8')
