#!/usr/bin/env python3
"""
Convert guide.md to guide.pdf using pypandoc (Windows-friendly).

Installation:
1. Install pandoc: https://pandoc.org/installing.html (Windows installer available)
   OR use: winget install pandoc
2. pip install pypandoc

Alternative method using pdfkit (if pypandoc doesn't work):
1. Download wkhtmltopdf: https://wkhtmltopdf.org/downloads.html
2. pip install pdfkit markdown
"""

from pathlib import Path
import sys
import subprocess
import shutil


def convert_with_pandoc_direct():
    """Convert using pandoc directly via subprocess (most reliable for Windows)."""
    import os

    # Check if pandoc is available
    pandoc_path = shutil.which('pandoc')
    if not pandoc_path:
        print("Error: pandoc not found in PATH")
        print("Install pandoc from: https://pandoc.org/installing.html")
        print("Or use: winget install pandoc")
        return False

    print(f"Using pandoc at: {pandoc_path}")

    # Check for wkhtmltopdf in common locations if not in PATH
    wkhtmltopdf_path = shutil.which('wkhtmltopdf')
    if not wkhtmltopdf_path:
        # Check common installation path
        common_path = r"C:\Program Files\wkhtmltopdf\bin\wkhtmltopdf.exe"
        if os.path.exists(common_path):
            # Temporarily add to PATH for this session
            os.environ['PATH'] = r"C:\Program Files\wkhtmltopdf\bin" + ";" + os.environ['PATH']
            wkhtmltopdf_path = common_path
            print(f"Found wkhtmltopdf at: {common_path}")
    else:
        print(f"Found wkhtmltopdf at: {wkhtmltopdf_path}")

    # Paths
    script_dir = Path(__file__).parent
    project_root = script_dir.parent
    md_path = project_root / "guide" / "guide.md"
    pdf_path = project_root / "guide" / "guide.pdf"

    print(f"Reading {md_path}...")

    if not md_path.exists():
        print(f"Error: {md_path} not found")
        return False

    # Create custom CSS for professional, minimal styling with Poppins font
    css_content = """
    @page {
        margin: 2.5cm 2cm;
        @bottom-center {
            content: counter(page) " / " counter(pages);
            font-family: 'Poppins', sans-serif;
            font-size: 9pt;
            color: #6b7280;
        }
    }

    body {
        font-family: 'Poppins', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
        font-size: 10pt;
        line-height: 1.6;
        color: #1f2937;
        max-width: 100%;
        margin: 0;
        padding: 0;
    }

    h1 {
        font-family: 'Poppins', sans-serif;
        font-weight: 600;
        font-size: 24pt;
        color: #111827;
        margin-top: 0;
        margin-bottom: 1.5em;
        padding-bottom: 0.3em;
        border-bottom: 1px solid #e5e7eb;
        letter-spacing: -0.02em;
    }

    h2 {
        font-family: 'Poppins', sans-serif;
        font-weight: 600;
        font-size: 16pt;
        color: #111827;
        margin-top: 2em;
        margin-bottom: 0.8em;
        letter-spacing: -0.01em;
    }

    h3 {
        font-family: 'Poppins', sans-serif;
        font-weight: 500;
        font-size: 12pt;
        color: #374151;
        margin-top: 1.5em;
        margin-bottom: 0.6em;
    }

    p {
        margin-top: 0;
        margin-bottom: 0.8em;
    }

    code {
        font-family: 'Consolas', 'Monaco', 'Courier New', monospace;
        font-size: 9pt;
        background-color: #f3f4f6;
        color: #1f2937;
        padding: 2px 6px;
        border-radius: 3px;
    }

    pre {
        font-family: 'Consolas', 'Monaco', 'Courier New', monospace;
        font-size: 9pt;
        background-color: #f9fafb;
        border: 1px solid #e5e7eb;
        border-left: 3px solid #9ca3af;
        padding: 12px 16px;
        margin: 1em 0;
        border-radius: 4px;
        overflow-x: auto;
    }

    pre code {
        background-color: transparent;
        padding: 0;
        border-radius: 0;
    }

    table {
        border-collapse: collapse;
        width: 100%;
        margin: 1.2em 0;
        font-size: 9.5pt;
    }

    th {
        font-family: 'Poppins', sans-serif;
        font-weight: 500;
        background-color: #f9fafb;
        color: #374151;
        text-align: left;
        padding: 10px 12px;
        border-bottom: 2px solid #e5e7eb;
    }

    td {
        padding: 8px 12px;
        border-bottom: 1px solid #e5e7eb;
        color: #4b5563;
    }

    tr:last-child td {
        border-bottom: none;
    }

    strong {
        font-weight: 600;
        color: #111827;
    }

    ul, ol {
        margin: 0.6em 0;
        padding-left: 1.8em;
    }

    li {
        margin-bottom: 0.4em;
    }

    blockquote {
        border-left: 3px solid #d1d5db;
        margin: 1em 0;
        padding-left: 1em;
        color: #6b7280;
    }

    #TOC {
        font-family: 'Poppins', sans-serif;
        background-color: #f9fafb;
        padding: 20px 24px;
        margin-bottom: 2em;
        border-radius: 6px;
        border: 1px solid #e5e7eb;
    }

    #TOC ul {
        list-style: none;
        padding-left: 0;
    }

    #TOC li {
        margin-bottom: 0.5em;
    }

    #TOC a {
        color: #374151;
        text-decoration: none;
    }

    #TOC a:hover {
        color: #111827;
    }
    """

    # Write CSS to temporary file
    css_path = project_root / "guide" / ".temp_pdf_style.css"
    with open(css_path, 'w', encoding='utf-8') as f:
        f.write(css_content)

    # Try different PDF engines in order of preference
    pdf_engines = ['wkhtmltopdf', 'pdflatex', 'xelatex', 'weasyprint']

    for engine in pdf_engines:
        print(f"Trying PDF engine: {engine}...")

        # Build pandoc command
        cmd = [
            pandoc_path,
            str(md_path),
            '-o', str(pdf_path),
            f'--pdf-engine={engine}',
            '--css', str(css_path),
        ]

        # Add engine-specific options
        if engine == 'wkhtmltopdf':
            # wkhtmltopdf specific options for better quality
            cmd.extend([
                '--pdf-engine-opt=--enable-local-file-access',
                '--pdf-engine-opt=--print-media-type',
                '--pdf-engine-opt=--no-background',
            ])
        elif 'latex' in engine:
            # LaTeX-based engines
            cmd.extend([
                '-V', 'geometry:margin=2.5cm',
                '-V', 'fontsize=10pt',
                '-V', 'mainfont=Poppins',
                '-V', 'monofont=Consolas',
                '--syntax-highlighting=tango'
            ])

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8',
                                   errors='replace', check=True)

            print(f"PDF generated successfully with {engine}: {pdf_path}")
            print(f"  File size: {pdf_path.stat().st_size / 1024:.1f} KB")

            # Clean up temporary CSS file
            try:
                css_path.unlink()
            except:
                pass

            return True

        except subprocess.CalledProcessError as e:
            # Try next engine if this one fails
            if e.stderr and 'not found' in e.stderr.lower():
                print(f"  {engine} not available, trying next...")
                continue
            else:
                error_msg = e.stderr if e.stderr else 'Unknown error'
                print(f"  Error with {engine}: {error_msg}")
                continue
        except Exception as e:
            print(f"  Error with {engine}: {e}")
            continue

    # If all engines failed, clean up CSS file
    try:
        css_path.unlink()
    except:
        pass

    # If all engines failed
    print("Error: No suitable PDF engine found")
    print("Install one of the following:")
    print("  - LaTeX distribution (MiKTeX or TeX Live): https://www.latex-project.org/get/")
    print("  - wkhtmltopdf: https://wkhtmltopdf.org/downloads.html")
    return False


def convert_with_pypandoc():
    """Convert using pypandoc (recommended for Windows)."""
    try:
        import pypandoc
    except ImportError:
        print("Error: pypandoc not installed")
        print("Run: pip install pypandoc")
        print("Also install pandoc: https://pandoc.org/installing.html")
        return False

    # Explicitly set pandoc path for Windows
    import os
    import shutil

    # Try to find pandoc in PATH first
    pandoc_in_path = shutil.which('pandoc')
    if pandoc_in_path:
        # Set pypandoc to use the pandoc found in PATH
        try:
            # This tells pypandoc where to find pandoc
            pypandoc.set_pandoc_path(pandoc_in_path)
            print(f"Using pandoc at: {pandoc_in_path}")
        except Exception as e:
            print(f"Warning: Could not set pandoc path: {e}")
    else:
        # Fallback to default Windows location
        pandoc_path = r"C:\Users\gregor\AppData\Local\Pandoc\pandoc.exe"
        if os.path.exists(pandoc_path):
            pypandoc.set_pandoc_path(pandoc_path)
            print(f"Using pandoc at: {pandoc_path}")

    # Paths
    script_dir = Path(__file__).parent
    project_root = script_dir.parent
    md_path = project_root / "guide" / "guide.md"
    pdf_path = project_root / "guide" / "guide.pdf"

    print(f"Reading {md_path}...")

    # PDF options for better formatting
    extra_args = [
        '--pdf-engine=xelatex',  # Better Unicode support
        '-V', 'geometry:margin=2.5cm',
        '-V', 'fontsize=10pt',
        '-V', 'mainfont=Arial',
        '-V', 'monofont=Courier New',
        '--toc',  # Table of contents
        '--toc-depth=2',
        '--highlight-style=tango'
    ]

    try:
        print("Converting to PDF...")
        pypandoc.convert_file(
            str(md_path),
            'pdf',
            outputfile=str(pdf_path),
            extra_args=extra_args
        )

        print(f"✓ PDF generated successfully: {pdf_path}")
        print(f"  File size: {pdf_path.stat().st_size / 1024:.1f} KB")
        return True

    except RuntimeError as e:
        if "pandoc" in str(e).lower():
            print("Error: pandoc not found")
            print("Install pandoc from: https://pandoc.org/installing.html")
            print("Or use: winget install pandoc")
        else:
            print(f"Error: {e}")
        return False


def convert_with_pdfkit():
    """Fallback method using pdfkit."""
    try:
        import pdfkit
        import markdown
    except ImportError:
        print("Error: pdfkit or markdown not installed")
        print("Run: pip install pdfkit markdown")
        return False

    # Paths
    script_dir = Path(__file__).parent
    project_root = script_dir.parent
    md_path = project_root / "guide" / "guide.md"
    pdf_path = project_root / "guide" / "guide.pdf"

    print(f"Reading {md_path}...")
    with open(md_path, 'r', encoding='utf-8') as f:
        md_content = f.read()

    print("Converting markdown to HTML...")
    md = markdown.Markdown(extensions=['tables', 'fenced_code'])
    html_content = md.convert(md_content)

    # Simple CSS styling
    html_document = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <style>
            body {{
                font-family: Arial, sans-serif;
                font-size: 10pt;
                line-height: 1.5;
                margin: 2cm;
            }}
            h1 {{
                font-size: 18pt;
                border-bottom: 2px solid black;
                padding-bottom: 5px;
            }}
            h2 {{
                font-size: 14pt;
                margin-top: 20px;
            }}
            h3 {{
                font-size: 12pt;
            }}
            code {{
                font-family: "Courier New", monospace;
                background-color: #f5f5f5;
                padding: 2px 4px;
            }}
            pre {{
                font-family: "Courier New", monospace;
                background-color: #f5f5f5;
                padding: 10px;
                border-left: 3px solid #ccc;
            }}
            table {{
                border-collapse: collapse;
                width: 100%;
                margin: 10px 0;
            }}
            th, td {{
                border: 1px solid #ccc;
                padding: 6px 8px;
                text-align: left;
            }}
            th {{
                background-color: #e0e0e0;
            }}
        </style>
    </head>
    <body>
        {html_content}
    </body>
    </html>
    """

    try:
        print("Converting to PDF...")
        options = {
            'page-size': 'A4',
            'margin-top': '2.5cm',
            'margin-right': '2cm',
            'margin-bottom': '2cm',
            'margin-left': '2cm',
            'encoding': 'UTF-8',
            'footer-center': '[page] of [topage]',
            'footer-font-size': '9'
        }

        pdfkit.from_string(html_document, str(pdf_path), options=options)

        print(f"✓ PDF generated successfully: {pdf_path}")
        print(f"  File size: {pdf_path.stat().st_size / 1024:.1f} KB")
        return True

    except OSError as e:
        if "wkhtmltopdf" in str(e):
            print("Error: wkhtmltopdf not found")
            print("Download from: https://wkhtmltopdf.org/downloads.html")
        else:
            print(f"Error: {e}")
        return False


def main():
    """Try conversion methods in order of preference."""
    print("Serial Router Guide - PDF Conversion")
    print("=" * 50)

    # Try direct pandoc first (most reliable)
    print("\nAttempting conversion with pandoc...")
    if convert_with_pandoc_direct():
        return

    print("\n" + "=" * 50)
    print("Direct pandoc failed, trying pypandoc...")
    if convert_with_pypandoc():
        return

    print("\n" + "=" * 50)
    print("pypandoc failed, trying pdfkit...")
    if convert_with_pdfkit():
        return

    print("\n" + "=" * 50)
    print("All conversion methods failed.")
    print("\nQuick setup for pandoc (recommended):")
    print("  1. winget install pandoc")
    print("  2. Ensure pandoc is in your PATH (restart terminal if needed)")
    print("\nOR for pypandoc:")
    print("  1. winget install pandoc")
    print("  2. pip install pypandoc")
    print("\nOR for pdfkit:")
    print("  1. Download wkhtmltopdf: https://wkhtmltopdf.org/downloads.html")
    print("  2. pip install pdfkit markdown")
    sys.exit(1)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nConversion cancelled")
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error: {e}")
        sys.exit(1)
