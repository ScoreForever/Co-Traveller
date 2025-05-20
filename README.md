# Co-Traveller

A group assignment for Peking University, an agent that helps you make travel plans.

## 依赖说明

本项目需要以下依赖：

1. **Pandoc**
    - 用于 Markdown 转 PDF（可选方案）。
    - 请从 [Pandoc 官网](https://pandoc.org/installing.html) 下载并安装。
    - 安装后请确保 `pandoc` 命令已加入环境变量 PATH，否则无法直接在命令行或 bat 脚本中调用。

2. **wkhtmltopdf**
    - 用于 Markdown 转 PDF（推荐方案，配合 `md2pdf_wkhtmltopdf.py` 使用）。
    - 请从 [wkhtmltopdf 官网](https://wkhtmltopdf.org/downloads.html) 下载并安装。
    - 安装后请确保其可执行文件路径在下列常见路径之一，或已添加到环境变量 PATH 中：
        - Windows:  
          `C:\Program Files\wkhtmltopdf\bin\wkhtmltopdf.exe`  
          `C:\Program Files (x86)\wkhtmltopdf\bin\wkhtmltopdf.exe`
        - Linux/macOS:  
          `/usr/local/bin/wkhtmltopdf`  
          `/usr/bin/wkhtmltopdf`

3. **Python 依赖包**
    - 请通过 pip 安装：
      ```
      pip install -r requirements.txt
      ```
    - 主要依赖：
        - `markdown`
        - `pdfkit`

如需更多帮助，请参考各工具的官方文档。
