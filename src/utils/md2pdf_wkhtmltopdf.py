import sys
import os

def md_to_pdf(md_path, pdf_path, css_path=None):
    import markdown
    import pdfkit
    from pdfkit.configuration import Configuration

    # 自动查找wkhtmltopdf路径
    wkhtmltopdf_path = None
    possible_paths = [
        r"C:\Program Files\wkhtmltopdf\bin\wkhtmltopdf.exe",
        r"C:\Program Files (x86)\wkhtmltopdf\bin\wkhtmltopdf.exe",
        "/usr/local/bin/wkhtmltopdf",
        "/usr/bin/wkhtmltopdf",
        r"D:\wkhtmltopdf\bin\wkhtmltopdf.exe",
        r"F:\北京大学\人工智能基础\大作业\外部库\wkhtmltopdf\bin\wkhtmltopdf.exe"
    ]
    for path in possible_paths:
        if os.path.exists(path):
            wkhtmltopdf_path = path
            break

    if wkhtmltopdf_path is None:
        print("未找到wkhtmltopdf可执行文件，请先安装wkhtmltopdf并确保其在上述常见路径或添加到环境变量PATH中。")
        print("下载地址：https://wkhtmltopdf.org/downloads.html")
        sys.exit(1)

    config = Configuration(wkhtmltopdf=wkhtmltopdf_path)

    with open(md_path, "r", encoding="utf-8") as f:
        md_text = f.read()
    html = markdown.markdown(md_text, output_format="html5")

    # 默认中文+emoji字体CSS
    default_font_css = """
    body {
        font-family: "Segoe UI Emoji", "Noto Color Emoji", "Apple Color Emoji",
                     "Microsoft YaHei", "SimSun", "SimHei", "Arial Unicode MS", Arial, sans-serif;
        font-size: 16px;
        line-height: 1.7;
        word-break: break-all;
        color: #222;
        background: #fff;
        margin: 2em;
    }
    h1, h2, h3, h4, h5, h6 {
        font-family: inherit;
        font-weight: bold;
        margin-top: 1.5em;
        margin-bottom: 0.5em;
    }
    p {
        margin: 1em 0;
    }
    /* emoji 单独处理，优先彩色字体 */
    .emoji, span.emoji {
        font-family: "Segoe UI Emoji", "Noto Color Emoji", "Apple Color Emoji", sans-serif;
    }
    """

    # 如果有自定义CSS，插入到HTML头部，并补充中文字体
    if css_path and os.path.exists(css_path):
        with open(css_path, "r", encoding="utf-8") as f:
            css = f.read()
        if "font-family" not in css:
            css = default_font_css + css
        html = f"""<html>
<head>
<meta charset="utf-8">
<style>{css}</style>
</head>
<body>{html}</body>
</html>"""
    else:
        html = f"""<html>
<head>
<meta charset="utf-8">
<style>{default_font_css}</style>
</head>
<body>{html}</body>
</html>"""

    pdfkit.from_string(html, pdf_path, configuration=config)

if __name__ == "__main__":
    # 输入路径
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    md_path = os.path.join(base_dir, "temp", "travel_plans", "tourGuide.md")
    # 输出路径
    guides_dir = os.path.join(base_dir, "travel_guides")
    if not os.path.exists(guides_dir):
        os.makedirs(guides_dir, exist_ok=True)
    pdf_path = os.path.join(guides_dir, "tourGuide.pdf")
    css_path = os.path.join(os.path.dirname(__file__), "markdown.css")  # 可选：自定义CSS文件
    if not os.path.exists(md_path):
        print("输入的md文件不存在")
        sys.exit(1)
    # 检查常用中文字体
    import platform
    if platform.system() == "Windows":
        font_paths = [
            r"C:\Windows\Fonts\msyh.ttc",
            r"C:\Windows\Fonts\simsun.ttc",
            r"C:\Windows\Fonts\simhei.ttf"
        ]
    else:
        font_paths = [
            "/usr/share/fonts/truetype/arphic/ukai.ttc",
            "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc"
        ]
    if not any(os.path.exists(fp) for fp in font_paths):
        print("警告：未检测到常用中文字体，PDF可能仍然乱码。请安装如“微软雅黑”“宋体”等中文字体。")
        print("如果 emoji 仍为黑白，请安装支持彩色 emoji 的字体，如 Windows 的 Segoe UI Emoji、Linux 的 Noto Color Emoji。")
    md_to_pdf(md_path, pdf_path, css_path)
    print(f"已生成PDF: {pdf_path}")
